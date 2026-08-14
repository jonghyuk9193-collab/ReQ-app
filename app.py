import streamlit as st
import pymysql
import json
import datetime
import os
from fpdf import FPDF
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- [포맷팅 함수 선언] ---
def format_phone_str(phone_str):
    if not phone_str: return ""
    nums = "".join(filter(str.isdigit, str(phone_str)))
    if len(nums) == 11: return f"{nums[:3]}-{nums[3:7]}-{nums[7:]}"
    if len(nums) == 10:
        if nums.startswith("02"): return f"{nums[:2]}-{nums[2:6]}-{nums[6:]}"
        return f"{nums[:3]}-{nums[3:6]}-{nums[6:]}"
    if len(nums) == 9 and nums.startswith("02"): return f"{nums[:2]}-{nums[2:5]}-{nums[5:]}"
    if len(nums) == 8: return f"{nums[:4]}-{nums[4:]}"
    return phone_str 

def format_money_str(money_str):
    if not money_str: return ""
    nums = "".join(filter(str.isdigit, str(money_str)))
    return f"{int(nums):,}" if nums else ""

# --- [상태 변경 콜백 함수] ---
def on_phone_change():
    st.session_state.hosp_phone = format_phone_str(st.session_state.hosp_phone)

def on_cost_change():
    st.session_state.cost_val = format_money_str(st.session_state.cost_val)

def on_contract_change():
    st.session_state.contract_val = format_money_str(st.session_state.contract_val)

def on_extra_phone_change(key):
    st.session_state[key] = format_phone_str(st.session_state[key])

# --- [DB 설정] ---
DB_HOST = "dev.mdpeople.co.kr"
DB_PORT = 13306
DB_USER = "jhlee"
DB_PW = st.secrets["DB_PW"]
DB_NAME = "MrbInvenDB"

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PW,
        database=DB_NAME, charset="utf8mb4"
    )

# --- 기본 데이터 로드 ---
@st.cache_data(ttl=600)
def load_services():
    default_services = ["Ncloud", "화이트디펜더", "MD마약", "백신온도계", "MD검진", "법정교육", "케어포미(PHR)", "MDPAD(앱)+의뢰회송", "비대면진료", "검사실예약", "CDSS", "DeepChest", "MaaD", "옵시", "해시계", "노티", "팔로", "링크"]
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT service_name FROM ReQ ORDER BY id ASC")
            rows = cursor.fetchall()
            if rows: return [row[0] for row in rows]
    except:
        pass
    return default_services

@st.cache_data(ttl=600)
def load_managers():
    default_managers = ["정광철", "고일민", "윤재선"]
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT manager_name FROM ManagerList ORDER BY id ASC")
            rows = cursor.fetchall()
            if rows: return [row[0] for row in rows]
    except:
        pass
    return default_managers

# --- 세션 상태 초기화 ---
if 'extra_managers' not in st.session_state: st.session_state.extra_managers = []
if 'hosp_phone' not in st.session_state: st.session_state.hosp_phone = ""
if 'cost_val' not in st.session_state: st.session_state.cost_val = ""
if 'contract_val' not in st.session_state: st.session_state.contract_val = ""

def add_manager():
    st.session_state.extra_managers.append({"name": "", "phone": ""})

# --- UI 레이아웃 설정 ---
st.set_page_config(page_title="미라벨소프트 - 설치 의뢰서 생성기", layout="wide")
st.title("🏥 미라벨소프트 - 설치 의뢰서 생성기")

# 상단 작성자 정보 (수동입력 기능 추가)
col_top1, col_top2 = st.columns(2)
with col_top1:
    manager_list = ["선택", "직접입력"] + load_managers()
    manager_sel = st.selectbox("영업 담당자", manager_list)
    if manager_sel == "직접입력":
        manager_val = st.text_input("영업 담당자 (직접입력)")
    else:
        manager_val = "" if manager_sel == "선택" else manager_sel

with col_top2:
    author_list = ["선택", "직접입력", "정광철", "고일민", "윤재선", "김덕훈", "이종혁", "박건우", "김정수", "정종훈", "임홍근"]
    author_sel = st.selectbox("작성자", author_list)
    if author_sel == "직접입력":
        author_val = st.text_input("작성자 (직접입력)")
    else:
        author_val = "" if author_sel == "선택" else author_sel

st.divider()

# --- 1. 기본 정보 입력 ---
st.subheader("📋 1. 기본 정보 입력")

col1, col2, col3 = st.columns(3)
with col1: hospital_name = st.text_input("병원명(필수)*")
with col2: install_addr = st.text_input("설치 주소")
with col3: biz_num = st.text_input("사업자번호")

col4, col5, col6 = st.columns(3)
with col4: care_num = st.text_input("요양기관번호")
with col5: install_date = st.date_input("설치 날짜", value=None)
with col6: install_time = st.time_input("설치 시간", value=None)

col7, col8, col9 = st.columns(3)
with col7: stab_date = st.date_input("안정화 날짜", value=None)
with col8: hosp_manager = st.text_input("병원 담당자 (이름/직급)")
with col9: hosp_phone = st.text_input("담당자 연락처 (숫자만 입력시 자동변환)", key="hosp_phone", on_change=on_phone_change)

col10, col11, col12 = st.columns(3)
with col10: cost_input = st.text_input("원가 (숫자만 입력시 자동변환)", key="cost_val", on_change=on_cost_change)
with col11: contract_input = st.text_input("계약금액(VAT) (숫자만 입력시 자동변환)", key="contract_val", on_change=on_contract_change)
with col12: 
    # 할인율 계산을 위해 문자열에서 쉼표 제거 후 정수형으로 변환
    cost_num = int("".join(filter(str.isdigit, cost_input)) or 0)
    contract_num = int("".join(filter(str.isdigit, contract_input)) or 0)
    
    discount_rate = 0.0
    if cost_num > 0:
        discount_rate = ((cost_num - contract_num) / cost_num) * 100
    st.metric(label="할인율", value=f"{discount_rate:.1f}%")

discount_remark = st.text_input("할인 사유")

# 추가 담당자
st.button("➕ 추가 담당자 등록", on_click=add_manager)
extra_manager_data = []
for i, mgr in enumerate(st.session_state.extra_managers):
    c1, c2 = st.columns(2)
    phone_key = f"mgr_phone_{i}"
    
    # 추가 담당자의 폰번호 초기 상태가 없으면 빈 문자열로 생성
    if phone_key not in st.session_state:
        st.session_state[phone_key] = ""
        
    with c1:
        m_name = st.text_input(f"추가 담당자 이름 {i+1}", key=f"mgr_name_{i}")
    with c2:
        m_phone = st.text_input(f"추가 담당자 연락처 {i+1} (자동변환)", key=phone_key, on_change=on_extra_phone_change, args=(phone_key,))
    extra_manager_data.append({"name": m_name, "phone": m_phone})

st.divider()

# --- 2. 도입 프로그램 세부 사항 ---
st.subheader("💻 2. 도입 프로그램")

prog_col1, prog_col2, prog_col3, prog_col4 = st.columns(4)
with prog_col1: use_mdpacs = st.checkbox("MDPACS")
with prog_col2: use_migration = st.checkbox("마이그레이션")
with prog_col3: use_mdauto = st.checkbox("MD오토게이트")
with prog_col4: use_mdendo = st.checkbox("MD엔도클린")

prog_col5, prog_col6, prog_col7, _ = st.columns(4)
with prog_col5: use_eprescribe = st.checkbox("전자처방전")
with prog_col6: use_mdsilver = st.checkbox("MD실버")
with prog_col7: use_other = st.checkbox("기타장비")

# 각 프로그램별 상세 입력 (체크 시에만 보임)
mdpacs_selections = {}
mdpacs_remark = ""
ncloud_hdd = ""
hw_hdd = ""
hw_monitor = False
hw_price = ""

if use_mdpacs:
    st.write("**■ MDPACS 부가서비스 및 H/W**")
    
    # 1. H/W 납품 먼저 배치
    hw_col1, hw_col2, hw_col3, hw_col4 = st.columns(4)
    with hw_col1: hw_납품 = st.checkbox("H/W 납품")
    if hw_납품:
        with hw_col2: hw_hdd = st.selectbox("용량", ["1TB", "2TB", "3TB", "4TB", "8TB"])
        with hw_col3: hw_monitor = st.checkbox("모니터 포함")
        with hw_col4: hw_price = st.text_input("납품금액")

    # 2. 나머지 부가서비스 배치 (요청하신 순서 강제 적용)
    db_services = load_services()
    ordered_services = [
        "Ncloud", "화이트디펜더", "MD마약", "백신온도계", "MD검진", 
        "법정교육", "케어포미(PHR)", "MDPAD(앱)+의뢰회송", "비대면진료", 
        "검사실예약", "CDSS", "DeepChest", "MaaD", "옵시", 
        "해시계", "노티", "팔로", "링크"
    ]
    
    for srv in db_services:
        if srv not in ordered_services:
            ordered_services.append(srv)

    for i in range(0, len(ordered_services), 5):
        row_cols = st.columns(5)
        for j in range(5):
            idx = i + j
            if idx < len(ordered_services):
                srv = ordered_services[idx]
                with row_cols[j]:
                    mdpacs_selections[srv] = st.checkbox(srv, key=f"srv_{srv}")
                    if srv == "Ncloud" and mdpacs_selections[srv]:
                        ncloud_hdd = st.selectbox("Ncloud 용량", ["1TB", "2TB", "3TB", "4TB", "8TB"], key="ncloud_combo")
    
    mdpacs_remark = st.text_area("MDPACS 비고", height=68)

migration_company = ""
migration_cost = ""
migration_remark = ""
if use_migration:
    st.write("**■ 마이그레이션 세부정보**")
    m_col1, m_col2 = st.columns(2)
    with m_col1: migration_company = st.text_input("PACS 업체(수동입력)")
    with m_col2: migration_cost = st.text_input("마이그레이션 비용")
    migration_remark = st.text_area("마이그레이션 비고", height=68)

mdauto_hw = False
mdauto_monitor = False
mdauto_hw_price = ""
mdauto_type = ""
mdauto_model = ""
mdauto_manager = ""
mdauto_remark = ""
if use_mdauto:
    st.write("**■ MD오토게이트 세부정보 및 H/W**")
    a_col1, a_col2, a_col3 = st.columns(3)
    with a_col1: mdauto_hw = st.checkbox("H/W 납품", key="auto_hw")
    if mdauto_hw:
        with a_col2: mdauto_monitor = st.checkbox("모니터 포함", key="auto_mon")
        with a_col3: mdauto_hw_price = st.text_input("납품금액", key="auto_price")
        
    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1: mdauto_type = st.selectbox("연결 타입", ["선택", "SDI", "DVI", "HDMI", "AIO", "모름"])
    with t_col2: mdauto_model = st.text_input("내시경장비모델명")
    with t_col3: mdauto_manager = st.text_input("내시경장비업체 담당자")
    mdauto_remark = st.text_area("MD오토게이트 비고", height=68)

mdendo_data = {}
mdendo_remark = ""
if use_mdendo:
    st.write("**■ MD엔도클린 세부정보**")
    e_col1, e_col2, e_col3 = st.columns(3)
    with e_col1:
        mdendo_data["검사실 수"] = st.text_input("검사실 수")
        mdendo_data["내시경 장비 모델"] = st.text_input("내시경 장비 모델")
    with e_col2:
        mdendo_data["세척기 수"] = st.text_input("세척기 수")
        mdendo_data["GW프로그램 명"] = st.text_input("GW프로그램 명")
    with e_col3:
        mdendo_data["스코프 수"] = st.text_input("스코프 수")
    mdendo_remark = st.text_area("MD엔도클린 비고", height=68)

eprescribe_remark = ""
if use_eprescribe:
    st.write("**■ 전자처방전 세부정보**")
    eprescribe_remark = st.text_area("전자처방전 비고", height=68)

mdsilver_remark = ""
if use_mdsilver:
    st.write("**■ MD실버 세부정보**")
    mdsilver_remark = st.text_area("MD실버 비고", height=68)

other_equip_remark = ""
if use_other:
    st.write("**■ 기타장비 세부정보**")
    other_equip_remark = st.text_input("장비 내용/명칭")

st.divider()

# --- 3. CS팀에서 받을 서류 ---
st.subheader("📄 3. CS팀에서 받을 서류")
doc_cols = st.columns(4)
docs = ["계약서", "사업자등록증 & 이메일", "CMS동의서", "검수확인서"]
doc_selections = {}
for i, doc in enumerate(docs):
    with doc_cols[i]:
        doc_selections[doc] = st.checkbox(doc)

st.divider()

# --- 4. PDF 생성 및 Slack 전송 함수 ---
def build_pdf_document():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()
    
    font_path = "malgun.ttf"
    if not os.path.exists(font_path):
        st.error("오류: 코드 폴더에 'malgun.ttf' 폰트 파일이 없습니다. 윈도우 폰트 폴더에서 복사해 넣어주세요.")
        return None

    pdf.add_font("Malgun", "", font_path, uni=True)
    pdf.set_font("Malgun", "", 16)
    pdf.cell(0, 8, "[미라벨소프트] 설치 의뢰서", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Malgun", "", 10)
    pdf.cell(0, 6, "< 1. 병원 기본 정보 >", ln=True)
    
    pdf.cell(40, 6, "영업 담당자", border=1)
    pdf.cell(0, 6, f" {manager_val}", border=1, ln=True)
    pdf.cell(40, 6, "작성자", border=1)
    pdf.cell(0, 6, f" {author_val}", border=1, ln=True)
    
    info_map = {
        "병원명": hospital_name, "설치 주소": install_addr,
        "사업자번호": biz_num, "요양기관번호": care_num,
        "설치 날짜": f"{install_date} ({install_time})" if install_time else str(install_date),
        "안정화 날짜": str(stab_date), "담당자 이름": hosp_manager, "담당자 연락처": hosp_phone
    }
    for key, val in info_map.items():
        pdf.cell(40, 6, key, border=1)
        pdf.cell(0, 6, f" {val}", border=1, ln=True)

    for i, mgr in enumerate(extra_manager_data, start=2):
        if mgr["name"] or mgr["phone"]:
            pdf.cell(40, 6, f"담당자 이름 {i}", border=1)
            pdf.cell(0, 6, f" {mgr['name']}", border=1, ln=True)
            pdf.cell(40, 6, f"담당자 연락처 {i}", border=1)
            pdf.cell(0, 6, f" {mgr['phone']}", border=1, ln=True)

    pdf.cell(40, 6, "원가", border=1)
    pdf.cell(0, 6, f" {cost_num:,} 원", border=1, ln=True)
    pdf.cell(40, 6, "계약금액(VAT)", border=1)
    pdf.cell(0, 6, f" {contract_num:,} 원", border=1, ln=True)
    pdf.cell(40, 6, "할인율", border=1)
    pdf.cell(0, 6, f" {discount_rate:.1f}%", border=1, ln=True)
    
    if discount_remark:
        pdf.cell(40, 6, "할인 사유", border=1)
        pdf.cell(0, 6, f" {discount_remark}", border=1, ln=True)

    pdf.ln(3)
    pdf.cell(0, 6, "< 2. 도입 프로그램 세부 사항 >", ln=True)
    
    if use_mdpacs:
        pdf.cell(0, 6, "■ MDPACS", ln=True)
        
        if hw_납품:
            m_txt = "모니터 포함" if hw_monitor else "모니터 미포함"
            p_txt = f" / 납품금액: {hw_price}" if hw_price else ""
            pdf.cell(0, 6, f" - H/W 납품: HDD {hw_hdd} / {m_txt}{p_txt}", ln=True)
            
        sel_svcs = [k for k, v in mdpacs_selections.items() if v]
        if "Ncloud" in sel_svcs:
            sel_svcs[sel_svcs.index("Ncloud")] = f"Ncloud ({ncloud_hdd})"
        
        if sel_svcs:
            pdf.multi_cell(0, 6, f" - 부가서비스: {', '.join(sel_svcs)}")
            
        if mdpacs_remark:
            pdf.multi_cell(0, 6, f" - 비고: {mdpacs_remark}")
        pdf.ln(2)

    if use_migration:
        pdf.cell(0, 6, "■ 마이그레이션", ln=True)
        pdf.cell(0, 6, f" - PACS 업체: {migration_company}", ln=True)
        if migration_cost: pdf.cell(0, 6, f" - 비용: {migration_cost} 원", ln=True)
        if migration_remark: pdf.multi_cell(0, 6, f" - 비고: {migration_remark}")
        pdf.ln(2)

    if use_mdauto:
        pdf.cell(0, 6, "■ MD오토게이트", ln=True)
        if mdauto_hw:
            m_txt = "모니터 포함" if mdauto_monitor else "모니터 미포함"
            p_txt = f" / 납품금액: {mdauto_hw_price}" if mdauto_hw_price else ""
            pdf.cell(0, 6, f" - H/W 납품: {m_txt}{p_txt}", ln=True)
        pdf.cell(0, 6, f" - 연결 타입: {mdauto_type}", ln=True) 
        pdf.cell(0, 6, f" - 내시경장비 모델명: {mdauto_model}", ln=True)
        pdf.cell(0, 6, f" - 내시경장비업체 담당자: {mdauto_manager}", ln=True)
        if mdauto_remark: pdf.multi_cell(0, 6, f" - 비고: {mdauto_remark}")
        pdf.ln(2)

    if use_mdendo:
        pdf.cell(0, 6, "■ MD엔도클린", ln=True)
        for k, v in mdendo_data.items():
            pdf.cell(0, 6, f" - {k}: {v}", ln=True)
        if mdendo_remark: pdf.multi_cell(0, 6, f" - 비고: {mdendo_remark}")
        pdf.ln(2)

    if use_eprescribe and eprescribe_remark:
        pdf.cell(0, 6, "■ 전자처방전", ln=True)
        pdf.multi_cell(0, 6, f" - 비고: {eprescribe_remark}")
        pdf.ln(2)

    if use_mdsilver and mdsilver_remark:
        pdf.cell(0, 6, "■ MD실버", ln=True)
        pdf.multi_cell(0, 6, f" - 비고: {mdsilver_remark}")
        pdf.ln(2)
        
    if use_other and other_equip_remark:
        pdf.cell(0, 6, "■ 기타장비", ln=True)
        pdf.cell(0, 6, f" - 내용: {other_equip_remark}", ln=True)
        pdf.ln(2)

    pdf.cell(0, 6, "< 3. CS팀에서 받을 서류 >", ln=True)
    chk_docs = [k for k, v in doc_selections.items() if v]
    pdf.cell(0, 6, f" - 확인된 서류: {', '.join(chk_docs) if chk_docs else '없음'}", ln=True)

    return pdf

# 제출 버튼
if st.button("💬 Slack으로 전송하기", type="primary", use_container_width=True):
    if not hospital_name:
        st.error("병원명은 필수 입력 항목입니다.")
    else:
        pdf = build_pdf_document()
        if pdf:
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            m_name = manager_val if manager_val else "담당자미지정"
            temp_filename = f"{m_name}_{hospital_name}_{today_str}.pdf"
            
            try:
                pdf.output(temp_filename)
                
                sel_progs = []
                if use_mdpacs: sel_progs.append("MDPACS")
                if use_migration: sel_progs.append("마이그레이션")
                if use_mdauto: sel_progs.append("MD오토게이트")
                if use_mdendo: sel_progs.append("MD엔도클린")
                if use_eprescribe: sel_progs.append("전자처방전")
                if use_mdsilver: sel_progs.append("MD실버")
                if use_other: sel_progs.append("기타장비")
                progs_text = ", ".join(sel_progs) if sel_progs else "없음"
                
                a_name = author_val if author_val else "미지정"
                slack_msg = f"설치 의뢰서가 생성되었습니다\n도입프로그램 : {progs_text}\n병원명 : {hospital_name}\n작성자 : {a_name}"

                # 슬랙 전송
                SLACK_BOT_TOKEN = st.secrets["SLACK_BOT_TOKEN"]
                SLACK_CHANNEL_ID = "C0BNEP9BKDH" 
                client = WebClient(token=SLACK_BOT_TOKEN)
                
                response = client.files_upload_v2(
                    channel=SLACK_CHANNEL_ID,
                    file=temp_filename,
                    title=f"[{hospital_name}] 프로그램 설치 의뢰서",
                    initial_comment=slack_msg 
                )
                st.success("🎉 Slack 채널로 PDF가 성공적으로 전송되었습니다!")
                
            except SlackApiError as e:
                st.error(f"Slack 전송 실패: {e.response['error']}")
            except Exception as e:
                st.error(f"오류 발생: {e}")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
