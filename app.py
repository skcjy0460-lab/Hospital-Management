import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, date
import io
import hashlib

# ── 페이지 설정 ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="병원 경영진단 시스템",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS 스타일 ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
    
    * { font-family: 'Noto Sans KR', sans-serif; }
    
    .main-header {
        background: linear-gradient(135deg, #1a237e 0%, #0d47a1 50%, #1565c0 100%);
        padding: 2rem; border-radius: 12px; color: white; text-align: center;
        margin-bottom: 2rem; box-shadow: 0 4px 20px rgba(26,35,126,0.4);
    }
    .main-header h1 { font-size: 2.2rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .main-header p  { font-size: 1rem; opacity: 0.85; margin: 0.5rem 0 0; }

    .metric-card {
        background: white; border-radius: 10px; padding: 1.2rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08); border-left: 4px solid #1565c0;
        margin-bottom: 1rem;
    }
    .metric-card.danger  { border-left-color: #c62828; }
    .metric-card.warning { border-left-color: #f57f17; }
    .metric-card.success { border-left-color: #2e7d32; }

    .section-header {
        background: linear-gradient(90deg, #e3f2fd, #ffffff);
        border-left: 4px solid #1565c0; padding: 0.8rem 1.2rem;
        border-radius: 0 8px 8px 0; margin: 1.5rem 0 1rem; font-weight: 600;
        font-size: 1.1rem; color: #1a237e;
    }

    .free-badge  { background:#e8f5e9; color:#2e7d32; padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
    .pro-badge   { background:#fff3e0; color:#e65100; padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }
    .premium-badge { background:#fce4ec; color:#880e4f; padding:2px 10px; border-radius:20px; font-size:0.75rem; font-weight:600; }

    .report-box {
        background: #f8f9ff; border: 1px solid #c5cae9; border-radius: 10px;
        padding: 1.5rem; margin: 1rem 0; line-height: 1.8;
    }
    .ai-response {
        background: #fff8e1; border: 1px solid #ffe082; border-radius: 10px;
        padding: 1.5rem; margin: 1rem 0; line-height: 1.8;
    }
    .warning-box {
        background: #fff3e0; border: 1px solid #ffb74d; border-radius: 8px;
        padding: 1rem; margin: 0.5rem 0;
    }
    .danger-box {
        background: #ffebee; border: 1px solid #ef9a9a; border-radius: 8px;
        padding: 1rem; margin: 0.5rem 0;
    }
    .success-box {
        background: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 8px;
        padding: 1rem; margin: 0.5rem 0;
    }
    .lock-overlay {
        background: rgba(0,0,0,0.05); border: 2px dashed #bbb;
        border-radius: 10px; padding: 2rem; text-align: center;
        color: #888; margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab"] { font-size: 0.95rem; font-weight: 500; }
    .stTabs [aria-selected="true"] { color: #1565c0 !important; }
    .dataframe { font-size: 0.88rem !important; }
    
    .kpi-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:1rem; margin:1rem 0; }
    .kpi-item { background:white; border-radius:8px; padding:1rem; text-align:center;
                box-shadow:0 1px 6px rgba(0,0,0,0.07); }
    .kpi-value { font-size:1.6rem; font-weight:700; color:#1565c0; }
    .kpi-label { font-size:0.8rem; color:#666; margin-top:4px; }
    .kpi-delta { font-size:0.85rem; margin-top:2px; }
    .delta-pos { color:#2e7d32; } .delta-neg { color:#c62828; }

    /* 회계서식 숫자 공통 */
    .acct-num {
        font-family: 'Consolas', 'D2Coding', monospace;
        text-align: right; letter-spacing: 0.02em;
    }
    .acct-neg { color: #c62828; }   /* 음수 = 빨강+괄호 */
    .acct-pos { color: #1a237e; }   /* 양수 = 네이비 */
    .acct-zero{ color: #757575; }   /* 영 = 회색 */

    /* dataframe 숫자 셀 우측 정렬 강제 */
    [data-testid="stDataFrame"] td { text-align: right !important; }
    [data-testid="stDataFrame"] td:first-child { text-align: left !important; }
</style>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ─────────────────────────────────────────────────────────
for key, default in {
    "authenticated": False,
    "plan": "free",          # free | pro | premium
    "hospital_name": "",
    "data": {},
    "analysis_done": False,
    "ai_results": {},
    "api_keys": {"claude": "", "openai": "", "gemini": ""},
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── 헬퍼 함수 ────────────────────────────────────────────────────────────────
def fmt_krw(v):
    """회계서식: 천단위 콤마, 음수는 괄호 표기"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    if v < 0:
        return f"({abs(v):,.0f})"
    return f"{v:,.0f}"

def fmt_krw_short(v):
    """요약용 회계서식: 억/만 단위 축약, 음수 괄호 표기"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    neg = v < 0
    av  = abs(v)
    if av >= 1e8:
        s = f"{av/1e8:.2f}억"
    elif av >= 1e4:
        s = f"{av/1e4:,.0f}만"
    else:
        s = f"{av:,.0f}"
    return f"({s})" if neg else s

def fmt_krw_chart(v):
    """차트 툴팁/레이블용: 축약형, 음수 괄호 표기"""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    neg = v < 0
    av  = abs(v)
    if av >= 1e8:
        s = f"{av/1e8:.1f}억"
    elif av >= 1e4:
        s = f"{av/1e4:.0f}만"
    else:
        s = f"{av:,.0f}"
    return f"({s})" if neg else s

def apply_accounting_format(df, exclude_cols=None):
    """DataFrame의 숫자 금액 컬럼을 회계서식 문자열로 변환한 복사본 반환"""
    exclude_cols = set(exclude_cols or [])
    # 금액 컬럼으로 판단할 키워드
    money_keywords = ["매출","비용","급여","인건비","고정비","렌탈","유지보수","전기","수도",
                      "통신","보험","소모품","약제","장비","위생","광고","SNS","이벤트","합계",
                      "임차료","퇴직","인센티브","4대보험","소득세","마케팅","이익","수익",
                      "금액","처방","평균급여","월인건비"]
    result = df.copy()
    for col in result.columns:
        if col in exclude_cols:
            continue
        if not pd.api.types.is_numeric_dtype(result[col]):
            continue
        # 비율·횟수·건수·인원 컬럼은 제외
        skip_kw = ["횟수","건수","비율","점수","인원","율","수","회"]
        if any(k in col for k in skip_kw):
            continue
        # 금액 키워드가 포함되거나 숫자가 1,000원 이상인 경우 적용
        if any(k in col for k in money_keywords) or result[col].abs().median() >= 1000:
            result[col] = result[col].apply(fmt_krw)
    return result

def calc_score(ratio, thresholds):
    """thresholds: [(upper_bound, score), ...] 오름차순"""
    for ub, sc in thresholds:
        if ratio <= ub:
            return sc
    return thresholds[-1][1]

def color_score(s):
    if s >= 80: return "🟢"
    if s >= 60: return "🟡"
    if s >= 40: return "🟠"
    return "🔴"

# ── 데이터 로드 유틸 ─────────────────────────────────────────────────────────
def load_excel(uploaded_file):
    """업로드된 엑셀에서 시트별 DataFrame 딕셔너리 반환"""
    try:
        xl = pd.ExcelFile(uploaded_file)
        dfs = {}
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            df.columns = [str(c).strip() for c in df.columns]
            dfs[sheet] = df
        return dfs
    except Exception as e:
        st.error(f"엑셀 파일 로드 오류: {e}")
        return {}

# ── 샘플 데이터 생성 ─────────────────────────────────────────────────────────
def make_sample_data():
    months = [f"2024-{m:02d}" for m in range(1, 13)]
    np.random.seed(42)

    # 1. 인건비
    labor = pd.DataFrame({
        "월": months,
        "기본급합계(세전)": np.random.randint(28000000, 35000000, 12),
        "4대보험(사용자부담)": np.random.randint(2500000, 3200000, 12),
        "근로소득세": np.random.randint(800000, 1200000, 12),
        "인센티브": np.random.randint(0, 3000000, 12),
        "퇴직충당금": np.random.randint(2200000, 2800000, 12),
    })

    # 2. 고정비
    fixed = pd.DataFrame({
        "월": months,
        "임차료": [4500000]*12,
        "렌탈료": np.random.randint(1200000, 1600000, 12),
        "유지보수비": np.random.randint(300000, 800000, 12),
        "전기료": np.random.randint(400000, 700000, 12),
        "수도료": np.random.randint(80000, 150000, 12),
        "통신비": np.random.randint(200000, 350000, 12),
        "보험료": [350000]*12,
        "기타고정비": np.random.randint(200000, 500000, 12),
    })

    # 3. 장비/소모품/약제
    supply = pd.DataFrame({
        "월": months,
        "의료소모품": np.random.randint(1500000, 2500000, 12),
        "약제비": np.random.randint(2000000, 3500000, 12),
        "장비구입비": np.random.randint(0, 5000000, 12),
        "위생소모품": np.random.randint(200000, 500000, 12),
    })

    # 4. 월간 매출
    revenue = pd.DataFrame({
        "월": months,
        "급여매출": np.random.randint(25000000, 40000000, 12),
        "비급여매출": np.random.randint(8000000, 18000000, 12),
        "수납건수": np.random.randint(800, 1200, 12),
    })
    revenue["총매출"] = revenue["급여매출"] + revenue["비급여매출"]
    revenue["1인당평균처방금액"] = (revenue["총매출"] / revenue["수납건수"]).astype(int)

    # 5. 원무
    outpatient = pd.DataFrame({
        "월": months,
        "신환수": np.random.randint(60, 120, 12),
        "총내원환자수": np.random.randint(700, 1100, 12),
        "총내원횟수": np.random.randint(900, 1500, 12),
    })
    outpatient["1인당평균내원횟수"] = (outpatient["총내원횟수"] / outpatient["총내원환자수"]).round(2)
    outpatient["주상병1"] = ["상세불명의 고혈압"]*4 + ["2형 당뇨병"]*4 + ["급성기관지염"]*4
    outpatient["주상병2"] = ["고지혈증"]*6 + ["요통"]*6

    # 6. 직원 현황
    staff = pd.DataFrame({
        "직종": ["의사", "간호사", "간호조무사", "원무", "물리치료사", "방사선사"],
        "인원수": [2, 1, 3, 2, 1, 1],
        "평균급여(세전)": [8000000, 3500000, 2800000, 2600000, 3000000, 3200000],
    })

    # 7. 마케팅/홍보비
    marketing = pd.DataFrame({
        "월": months,
        "온라인광고비": np.random.randint(300000, 800000, 12),
        "오프라인광고비": np.random.randint(0, 300000, 12),
        "SNS운영비": np.random.randint(100000, 300000, 12),
        "이벤트비용": np.random.randint(0, 500000, 12),
    })

    # 8. 재무 요약
    finance = pd.DataFrame({
        "항목": ["의료수익", "의약품비", "재료비", "인건비", "관리비", "감가상각비", "금융비용"],
        "금액(연간)": [420000000, 28000000, 18000000, 380000000, 72000000, 12000000, 6000000],
    })

    return {
        "인건비": labor, "고정비": fixed, "소모품약제": supply,
        "매출": revenue, "원무": outpatient, "직원현황": staff,
        "마케팅": marketing, "재무요약": finance
    }

# ── 분석 엔진 ────────────────────────────────────────────────────────────────
def run_analysis(data):
    results = {}
    try:
        rev  = data.get("매출", pd.DataFrame())
        lab  = data.get("인건비", pd.DataFrame())
        fix  = data.get("고정비", pd.DataFrame())
        sup  = data.get("소모품약제", pd.DataFrame())
        out  = data.get("원무", pd.DataFrame())
        mkt  = data.get("마케팅", pd.DataFrame())
        fin  = data.get("재무요약", pd.DataFrame())

        # ── 매출 분석 ──────────────────────────────────────────────────────
        if not rev.empty and "총매출" in rev.columns:
            total_rev  = rev["총매출"].sum()
            avg_rev    = rev["총매출"].mean()
            rev_growth = (rev["총매출"].iloc[-1] / rev["총매출"].iloc[0] - 1) * 100 if len(rev) > 1 else 0
            nhi_ratio  = rev["급여매출"].sum() / total_rev * 100 if "급여매출" in rev.columns else 0
            results["revenue"] = {
                "total": total_rev, "monthly_avg": avg_rev,
                "growth_rate": rev_growth, "nhi_ratio": nhi_ratio,
                "non_nhi_ratio": 100 - nhi_ratio,
                "avg_prescription": rev["1인당평균처방금액"].mean() if "1인당평균처방금액" in rev.columns else 0,
            }
        else:
            results["revenue"] = {"total":0,"monthly_avg":0,"growth_rate":0,"nhi_ratio":0,"non_nhi_ratio":0,"avg_prescription":0}

        # ── 인건비 분석 ────────────────────────────────────────────────────
        if not lab.empty:
            lab_cols   = [c for c in ["기본급합계(세전)","4대보험(사용자부담)","근로소득세","인센티브","퇴직충당금"] if c in lab.columns]
            total_lab  = lab[lab_cols].sum().sum()
            rev_total  = results["revenue"]["total"]
            lab_ratio  = total_lab / rev_total * 100 if rev_total > 0 else 0
            results["labor"] = {
                "total": total_lab,
                "monthly_avg": total_lab / max(len(lab), 1),
                "ratio_to_revenue": lab_ratio,
                "score": calc_score(lab_ratio,
                    [(45,100),(50,85),(55,70),(60,55),(70,35),(200,15)])
            }
        else:
            results["labor"] = {"total":0,"monthly_avg":0,"ratio_to_revenue":0,"score":50}

        # ── 고정비 분석 ────────────────────────────────────────────────────
        if not fix.empty:
            fix_num    = fix.select_dtypes(include="number")
            total_fix  = fix_num.sum().sum()
            rev_total  = results["revenue"]["total"]
            fix_ratio  = total_fix / rev_total * 100 if rev_total > 0 else 0
            results["fixed"] = {
                "total": total_fix,
                "monthly_avg": total_fix / max(len(fix), 1),
                "ratio_to_revenue": fix_ratio,
                "score": calc_score(fix_ratio,
                    [(15,100),(20,80),(25,60),(30,40),(200,20)])
            }
        else:
            results["fixed"] = {"total":0,"monthly_avg":0,"ratio_to_revenue":0,"score":50}

        # ── 소모품/약제 분석 ──────────────────────────────────────────────
        if not sup.empty:
            sup_num    = sup.select_dtypes(include="number")
            total_sup  = sup_num.sum().sum()
            rev_total  = results["revenue"]["total"]
            sup_ratio  = total_sup / rev_total * 100 if rev_total > 0 else 0
            results["supply"] = {
                "total": total_sup,
                "monthly_avg": total_sup / max(len(sup), 1),
                "ratio_to_revenue": sup_ratio,
                "score": calc_score(sup_ratio,
                    [(10,100),(15,80),(20,60),(25,40),(200,20)])
            }
        else:
            results["supply"] = {"total":0,"monthly_avg":0,"ratio_to_revenue":0,"score":50}

        # ── 원무 분석 ─────────────────────────────────────────────────────
        if not out.empty:
            new_pt_ratio = (out["신환수"].sum() / out["총내원환자수"].sum() * 100
                            if "신환수" in out.columns and "총내원환자수" in out.columns else 0)
            avg_visits   = out["1인당평균내원횟수"].mean() if "1인당평균내원횟수" in out.columns else 0
            results["outpatient"] = {
                "total_patients": out["총내원환자수"].sum() if "총내원환자수" in out.columns else 0,
                "new_patient_ratio": new_pt_ratio,
                "avg_visits": avg_visits,
                "monthly_new": out["신환수"].mean() if "신환수" in out.columns else 0,
                "score": calc_score(new_pt_ratio,
                    [(5,50),(10,70),(15,85),(25,100),(200,90)])
            }
        else:
            results["outpatient"] = {"total_patients":0,"new_patient_ratio":0,"avg_visits":0,"monthly_new":0,"score":50}

        # ── 마케팅 비용 ───────────────────────────────────────────────────
        if not mkt.empty:
            mkt_num   = mkt.select_dtypes(include="number")
            total_mkt = mkt_num.sum().sum()
            rev_total = results["revenue"]["total"]
            results["marketing"] = {
                "total": total_mkt,
                "ratio_to_revenue": total_mkt / rev_total * 100 if rev_total > 0 else 0
            }
        else:
            results["marketing"] = {"total":0,"ratio_to_revenue":0}

        # ── 수익성 분석 ───────────────────────────────────────────────────
        total_cost = (results["labor"]["total"] + results["fixed"]["total"] +
                      results["supply"]["total"] + results["marketing"]["total"])
        total_rev  = results["revenue"]["total"]
        op_profit  = total_rev - total_cost
        op_margin  = op_profit / total_rev * 100 if total_rev > 0 else 0
        results["profitability"] = {
            "total_cost": total_cost,
            "op_profit": op_profit,
            "op_margin": op_margin,
            "score": calc_score(op_margin,
                [(0,20),(5,40),(10,60),(15,75),(20,90),(100,100)])
        }

        # ── 종합 점수 ─────────────────────────────────────────────────────
        weights = {
            "수익성":   (results["profitability"]["score"], 0.30),
            "인건비관리": (results["labor"]["score"],        0.25),
            "환자관리":  (results["outpatient"]["score"],   0.20),
            "고정비관리": (results["fixed"]["score"],        0.15),
            "원가관리":  (results["supply"]["score"],        0.10),
        }
        total_score = sum(s * w for s, w in weights.values())
        results["overall"] = {"score": total_score, "weights": weights}

    except Exception as e:
        st.error(f"분석 오류: {e}")

    return results

# ── AI 진단 함수 ─────────────────────────────────────────────────────────────
def call_claude(api_key, prompt):
    import anthropic
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"[Claude 오류] {e}"

def call_openai(api_key, prompt):
    from openai import OpenAI
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role":"system","content":"당신은 병원 경영 전문 컨설턴트입니다. 한국어로 상세하고 전문적인 진단 보고서를 작성합니다."},
                {"role":"user","content": prompt}
            ],
            max_tokens=4096
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"[OpenAI 오류] {e}"

def call_gemini(api_key, prompt):
    import google.generativeai as genai
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro")
        resp  = model.generate_content(prompt)
        return resp.text
    except Exception as e:
        return f"[Gemini 오류] {e}"

def build_ai_prompt(hospital_name, analysis, data):
    rev = analysis.get("revenue", {})
    lab = analysis.get("labor", {})
    fix = analysis.get("fixed", {})
    sup = analysis.get("supply", {})
    out = analysis.get("outpatient", {})
    pro = analysis.get("profitability", {})
    ovr = analysis.get("overall", {})

    prompt = f"""
당신은 대한민국 의원급 의료기관 경영 전문 컨설턴트입니다.
다음 병원 경영 데이터를 분석하여 매우 상세하고 전문적인 진단 보고서를 작성해 주세요.

【 병원명 】 {hospital_name}
【 분석기간 】 최근 12개월

═══════════════════════════════════════════
📊 핵심 경영지표 요약
═══════════════════════════════════════════
▶ 연간 총매출         : {fmt_krw(rev.get('total',0))}
▶ 월평균 매출         : {fmt_krw(rev.get('monthly_avg',0))}
▶ 매출성장률          : {rev.get('growth_rate',0):.1f}%
▶ 급여/비급여 비율    : {rev.get('nhi_ratio',0):.1f}% / {rev.get('non_nhi_ratio',0):.1f}%
▶ 1인당 평균처방금액  : {fmt_krw(rev.get('avg_prescription',0))}
▶ 인건비율            : {lab.get('ratio_to_revenue',0):.1f}% (연간 {fmt_krw(lab.get('total',0))})
▶ 고정비율            : {fix.get('ratio_to_revenue',0):.1f}% (연간 {fmt_krw(fix.get('total',0))})
▶ 원가(소모품+약제)율  : {sup.get('ratio_to_revenue',0):.1f}%
▶ 영업이익률          : {pro.get('op_margin',0):.1f}%  (영업이익: {fmt_krw(pro.get('op_profit',0))})
▶ 월평균 신환 수       : {out.get('monthly_new',0):.0f}명
▶ 신환비율            : {out.get('new_patient_ratio',0):.1f}%
▶ 1인당 평균내원횟수  : {out.get('avg_visits',0):.2f}회
▶ 종합 경영점수       : {ovr.get('score',0):.1f}/100점

═══════════════════════════════════════════
📋 요청 분석 항목
═══════════════════════════════════════════
아래 항목별로 상세히 분석해 주세요:

1. 【수익성 분석】
   - 현재 수익구조 평가 (급여/비급여 믹스 적정성)
   - 영업이익률 벤치마크 비교 (의원급 평균 대비)
   - 수익성 개선 우선순위 3가지

2. 【비용구조 분석】
   - 인건비율 적정성 평가 및 개선 방향
   - 고정비 절감 가능 영역 도출
   - 원가 관리 개선 포인트

3. 【환자 관리 분석】
   - 신환 유입 성과 평가
   - 환자 재내원율 분석
   - 환자 만족도 및 충성도 제고 전략

4. 【리스크 진단】
   - 단기 리스크 (3개월 이내)
   - 중기 리스크 (3~12개월)
   - 장기 리스크 (1년 이상)

5. 【전략적 개선 로드맵】
   - 즉시 실행 과제 (1개월 이내)
   - 단기 과제 (3개월 이내)
   - 중기 과제 (6~12개월)
   - 장기 비전 (1~3년)

6. 【벤치마크 비교】
   - 동종 의원급 평균 지표 대비 현황
   - 상위 20% 병원 수준 달성을 위한 GAP 분석

7. 【결론 및 핵심 제언】
   - 가장 중요한 3가지 핵심 개선 과제
   - 예상 개선 효과 (수치화)
   - 컨설턴트 종합 의견

각 항목에 대해 구체적인 수치와 근거를 제시하고, 실행 가능한 액션 플랜을 포함해 주세요.
보고서 형식으로 체계적으로 작성해 주세요.
"""
    return prompt

# ── 사이드바 ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 병원 경영진단 시스템")
    st.markdown("---")

    # 요금제 선택 (실제 서비스에서는 결제 시스템 연동)
    st.markdown("#### 💳 서비스 플랜")
    plan_map = {
        "🆓 무료 (Free)": "free",
        "⭐ 프로 (Pro)": "pro",
        "👑 프리미엄 (Premium)": "premium"
    }
    selected_plan = st.selectbox(
        "플랜 선택",
        list(plan_map.keys()),
        help="실제 서비스에서는 결제 완료 후 자동 활성화됩니다"
    )
    st.session_state.plan = plan_map[selected_plan]

    plan = st.session_state.plan
    if plan == "free":
        st.markdown("""
        <div style="background:#e8f5e9;padding:10px;border-radius:8px;font-size:0.82rem">
        ✅ 기본 데이터 입력<br>
        ✅ 기본 차트/그래프<br>
        ✅ 표준 경영지표<br>
        ❌ AI 심층진단<br>
        ❌ 상세 보고서<br>
        ❌ 벤치마크 비교<br>
        ❌ 전략 로드맵
        </div>""", unsafe_allow_html=True)
    elif plan == "pro":
        st.markdown("""
        <div style="background:#fff3e0;padding:10px;border-radius:8px;font-size:0.82rem">
        ✅ 무료 기능 전체<br>
        ✅ Claude AI 진단<br>
        ✅ GPT-4o 진단<br>
        ✅ 상세 전문 보고서<br>
        ✅ 벤치마크 비교<br>
        ❌ Gemini 진단<br>
        ❌ AI 통합 종합 의견<br>
        ❌ 맞춤형 로드맵
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#fce4ec;padding:10px;border-radius:8px;font-size:0.82rem">
        ✅ 프로 기능 전체<br>
        ✅ Gemini AI 진단<br>
        ✅ AI 3사 통합 의견<br>
        ✅ 맞춤형 전략 로드맵<br>
        ✅ PDF 보고서 출력<br>
        ✅ 월별 트렌드 분석<br>
        ✅ 우선순위 액션플랜
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### ⚙️ AI API 설정")
    if plan in ("pro", "premium"):
        st.session_state.api_keys["claude"]  = st.text_input("Claude API Key",  type="password", value=st.session_state.api_keys["claude"])
        st.session_state.api_keys["openai"]  = st.text_input("OpenAI API Key",  type="password", value=st.session_state.api_keys["openai"])
        if plan == "premium":
            st.session_state.api_keys["gemini"] = st.text_input("Gemini API Key", type="password", value=st.session_state.api_keys["gemini"])
        st.caption("⚠️ API 키는 세션 내에서만 사용되며 저장되지 않습니다.")
    else:
        st.info("Pro 이상 플랜에서 AI 진단 기능을 이용하실 수 있습니다.")

    st.markdown("---")
    st.markdown("#### 📁 데이터 업로드")
    use_sample = st.checkbox("샘플 데이터 사용", value=True)
    uploaded = None
    if not use_sample:
        uploaded = st.file_uploader("엑셀 파일 업로드", type=["xlsx","xls"])

    hospital_name = st.text_input("병원명", value="○○의원", placeholder="병원명 입력")
    st.session_state.hospital_name = hospital_name

    if st.button("🔍 분석 실행", use_container_width=True, type="primary"):
        with st.spinner("데이터 분석 중..."):
            if use_sample:
                st.session_state.data = make_sample_data()
            elif uploaded:
                st.session_state.data = load_excel(uploaded)
            else:
                st.warning("데이터를 업로드하거나 샘플 데이터를 선택하세요.")
                st.stop()

            st.session_state.analysis = run_analysis(st.session_state.data)
            st.session_state.analysis_done = True
            st.session_state.ai_results = {}
        st.success("✅ 분석 완료!")

# ── 메인 화면 ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
    <h1>🏥 병원 경영진단 시스템</h1>
    <p>Hospital Management Diagnosis & Strategy Platform | {hospital_name}</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.get("analysis_done"):
    # ── 랜딩 화면 ─────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="metric-card success">
        <h3>🆓 무료 기능</h3>
        <ul style="font-size:0.9rem">
        <li>기본 경영지표 시각화</li>
        <li>매출/비용 트렌드 차트</li>
        <li>표준 KPI 대시보드</li>
        <li>원무 현황 분석</li>
        </ul>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="metric-card warning">
        <h3>⭐ Pro 기능</h3>
        <ul style="font-size:0.9rem">
        <li>Claude + GPT-4o AI 진단</li>
        <li>전문 경영진단 보고서</li>
        <li>벤치마크 비교 분석</li>
        <li>개선 과제 도출</li>
        </ul>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="metric-card danger">
        <h3>👑 Premium 기능</h3>
        <ul style="font-size:0.9rem">
        <li>AI 3사 통합 진단</li>
        <li>맞춤형 전략 로드맵</li>
        <li>PDF 보고서 출력</li>
        <li>우선순위 액션플랜</li>
        </ul>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    ### 📋 데이터 입력 가이드

    좌측 사이드바에서 **샘플 데이터 사용** 을 선택하거나, 아래 양식에 맞춰 엑셀 파일을 업로드해 주세요.

    | 시트명 | 필수 컬럼 | 설명 |
    |--------|-----------|------|
    | 인건비 | 월, 기본급합계(세전), 4대보험(사용자부담), 근로소득세, 인센티브, 퇴직충당금 | 월별 인건비 내역 |
    | 고정비 | 월, 임차료, 렌탈료, 유지보수비, 전기료, 수도료, 통신비 | 월별 고정비 내역 |
    | 소모품약제 | 월, 의료소모품, 약제비, 장비구입비 | 월별 구매비용 |
    | 매출 | 월, 급여매출, 비급여매출, 수납건수 | 월별 매출 내역 |
    | 원무 | 월, 신환수, 총내원환자수, 총내원횟수, 주상병1 | 월별 원무 현황 |
    | 직원현황 | 직종, 인원수, 평균급여(세전) | 직원 구성 현황 |
    | 마케팅 | 월, 온라인광고비, 오프라인광고비, SNS운영비 | 마케팅 비용 |
    """)

    st.info("👈 좌측 사이드바에서 '샘플 데이터 사용'을 선택하고 **분석 실행** 버튼을 눌러주세요.")
    st.stop()

# ── 분석 결과 화면 ───────────────────────────────────────────────────────────
analysis = st.session_state.analysis
data     = st.session_state.data
plan     = st.session_state.plan

tabs = st.tabs([
    "📊 대시보드",
    "💰 매출분석",
    "👥 인건비분석",
    "🏢 비용구조",
    "🏥 원무분석",
    "📈 수익성분석",
    "🤖 AI 진단",
    "📋 종합보고서"
])

# ════════════════════════════════════════════════════════
# TAB 1: 대시보드
# ════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-header">📊 핵심 경영지표 대시보드 <span class="free-badge">FREE</span></div>', unsafe_allow_html=True)

    rev = analysis.get("revenue", {})
    lab = analysis.get("labor", {})
    pro = analysis.get("profitability", {})
    ovr = analysis.get("overall", {})
    out = analysis.get("outpatient", {})

    # KPI 카드
    c1,c2,c3,c4,c5 = st.columns(5)
    with c1:
        st.metric("연간 총매출", fmt_krw(rev.get("total",0)),
                  f"{rev.get('growth_rate',0):+.1f}% YoY")
    with c2:
        st.metric("영업이익률", f"{pro.get('op_margin',0):.1f}%",
                  "양호" if pro.get("op_margin",0)>10 else "개선필요")
    with c3:
        st.metric("인건비율", f"{lab.get('ratio_to_revenue',0):.1f}%",
                  "적정" if lab.get("ratio_to_revenue",0)<55 else "과다")
    with c4:
        st.metric("월평균 신환", f"{out.get('monthly_new',0):.0f}명",
                  f"신환비율 {out.get('new_patient_ratio',0):.1f}%")
    with c5:
        score = ovr.get("score",0)
        st.metric("종합 경영점수", f"{score:.0f}점 / 100점",
                  "우수" if score>=75 else ("양호" if score>=60 else "개선필요"))

    st.markdown("---")

    # 레이더 차트 + 월별 매출 추이
    col_a, col_b = st.columns([1, 1.5])
    with col_a:
        st.markdown("#### 🎯 영역별 경영점수")
        w_data = ovr.get("weights", {})
        if w_data:
            categories = list(w_data.keys())
            scores     = [v[0] for v in w_data.values()]
            fig_radar  = go.Figure(go.Scatterpolar(
                r=scores + [scores[0]],
                theta=categories + [categories[0]],
                fill='toself',
                fillcolor='rgba(21,101,192,0.2)',
                line=dict(color='#1565c0', width=2),
                marker=dict(size=6)
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                showlegend=False, height=320,
                margin=dict(l=30,r=30,t=20,b=20)
            )
            st.plotly_chart(fig_radar, use_container_width=True)

    with col_b:
        st.markdown("#### 📈 월별 매출 추이")
        rev_df = data.get("매출", pd.DataFrame())
        if not rev_df.empty and "총매출" in rev_df.columns:
            fig_rev = go.Figure()
            if "급여매출" in rev_df.columns:
                fig_rev.add_bar(
                    x=rev_df["월"], y=rev_df["급여매출"],
                    name="급여매출", marker_color="#1565c0",
                    hovertemplate="<b>%{x}</b><br>급여매출: %{customdata}<extra></extra>",
                    customdata=[fmt_krw(v) for v in rev_df["급여매출"]])
            if "비급여매출" in rev_df.columns:
                fig_rev.add_bar(
                    x=rev_df["월"], y=rev_df["비급여매출"],
                    name="비급여매출", marker_color="#42a5f5",
                    hovertemplate="<b>%{x}</b><br>비급여매출: %{customdata}<extra></extra>",
                    customdata=[fmt_krw(v) for v in rev_df["비급여매출"]])
            fig_rev.add_scatter(
                x=rev_df["월"], y=rev_df["총매출"],
                name="총매출", line=dict(color="#ff6f00", width=2.5),
                hovertemplate="<b>%{x}</b><br>총매출: %{customdata}<extra></extra>",
                customdata=[fmt_krw(v) for v in rev_df["총매출"]])
            fig_rev.update_layout(
                barmode="stack", height=320,
                margin=dict(l=0,r=0,t=20,b=0),
                legend=dict(orientation="h",y=-0.15),
                yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig_rev, use_container_width=True)

    # 비용 구성 파이차트
    st.markdown("#### 💸 연간 비용 구성")
    c1, c2 = st.columns(2)
    with c1:
        cost_items = {
            "인건비":  analysis["labor"]["total"],
            "고정비":  analysis["fixed"]["total"],
            "소모품/약제": analysis["supply"]["total"],
            "마케팅비": analysis["marketing"]["total"],
        }
        cost_items = {k:v for k,v in cost_items.items() if v>0}
        if cost_items:
            fig_pie = px.pie(values=list(cost_items.values()),
                             names=list(cost_items.keys()),
                             color_discrete_sequence=px.colors.sequential.Blues_r)
            fig_pie.update_layout(height=280, margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig_pie, use_container_width=True)
    with c2:
        # 원무 현황 요약
        out_df = data.get("원무", pd.DataFrame())
        if not out_df.empty and "총내원환자수" in out_df.columns:
            fig_pt = px.bar(out_df, x="월", y="총내원환자수",
                            color="신환수" if "신환수" in out_df.columns else None,
                            title="월별 내원환자 현황",
                            color_continuous_scale="Blues")
            fig_pt.update_layout(height=280, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig_pt, use_container_width=True)

# ════════════════════════════════════════════════════════
# TAB 2: 매출분석
# ════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-header">💰 매출 상세 분석 <span class="free-badge">FREE</span></div>', unsafe_allow_html=True)
    rev_df = data.get("매출", pd.DataFrame())

    if rev_df.empty:
        st.warning("매출 데이터가 없습니다.")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("연간 총매출", fmt_krw(rev_df["총매출"].sum()) if "총매출" in rev_df.columns else "-")
        c2.metric("월평균 매출", fmt_krw(rev_df["총매출"].mean()) if "총매출" in rev_df.columns else "-")
        c3.metric("최고 매출월", rev_df.loc[rev_df["총매출"].idxmax(),"월"] if "총매출" in rev_df.columns else "-")
        c4.metric("1인당 평균처방", fmt_krw(rev_df["1인당평균처방금액"].mean()) if "1인당평균처방금액" in rev_df.columns else "-")

        st.markdown("#### 매출 상세 데이터")
        st.dataframe(apply_accounting_format(rev_df, exclude_cols=["월","수납건수"]),
                     use_container_width=True, hide_index=True)

        if "급여매출" in rev_df.columns and "비급여매출" in rev_df.columns:
            col1, col2 = st.columns(2)
            with col1:
                fig = go.Figure()
                for col_name, color in [("급여매출","#1565c0"),("비급여매출","#42a5f5"),("총매출","#ff6f00")]:
                    if col_name in rev_df.columns:
                        fig.add_scatter(
                            x=rev_df["월"], y=rev_df[col_name],
                            name=col_name, mode="lines+markers",
                            line=dict(color=color, width=2),
                            hovertemplate=f"<b>%{{x}}</b><br>{col_name}: %{{customdata}}<extra></extra>",
                            customdata=[fmt_krw(v) for v in rev_df[col_name]])
                fig.update_layout(title="매출 트렌드", height=300,
                                  yaxis=dict(tickformat=",.0f"))
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                nhi_sum    = rev_df["급여매출"].sum()
                non_nhi    = rev_df["비급여매출"].sum()
                fig2 = go.Figure(go.Pie(
                    labels=["급여매출","비급여매출"],
                    values=[nhi_sum, non_nhi],
                    hole=0.4,
                    marker_colors=["#1565c0","#42a5f5"],
                    hovertemplate="<b>%{label}</b><br>금액: %{customdata}<br>비율: %{percent}<extra></extra>",
                    customdata=[fmt_krw(nhi_sum), fmt_krw(non_nhi)]
                ))
                fig2.update_layout(title="급여/비급여 비율", height=300)
                st.plotly_chart(fig2, use_container_width=True)

        if "1인당평균처방금액" in rev_df.columns:
            avg_pres = rev_df["1인당평균처방금액"].mean()
            fig3 = go.Figure(go.Bar(
                x=rev_df["월"], y=rev_df["1인당평균처방금액"],
                marker_color=rev_df["1인당평균처방금액"],
                marker_colorscale="Blues",
                hovertemplate="<b>%{x}</b><br>1인당 처방금액: %{customdata}<extra></extra>",
                customdata=[fmt_krw(v) for v in rev_df["1인당평균처방금액"]]))
            fig3.add_hline(y=avg_pres, line_dash="dash", line_color="red",
                           annotation_text=f"평균: {fmt_krw(avg_pres)}")
            fig3.update_layout(title="1인당 평균 처방금액 추이", height=280,
                               yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig3, use_container_width=True)

        if plan in ("pro", "premium"):
            st.markdown('<div class="section-header">📊 업종 벤치마크 비교 <span class="pro-badge">PRO</span></div>', unsafe_allow_html=True)
            avg_rev = rev_df["총매출"].mean() if "총매출" in rev_df.columns else 0
            avg_pres_val = rev_df["1인당평균처방금액"].mean() if "1인당평균처방금액" in rev_df.columns else 0
            bench = {
                "지표": ["월평균 매출","1인당 처방금액","비급여 비율"],
                "본원": [fmt_krw(avg_rev),
                         fmt_krw(avg_pres_val),
                         f"{analysis['revenue']['non_nhi_ratio']:.1f}%"],
                "업종 평균": [fmt_krw(32000000), fmt_krw(42000), "28.0%"],
                "상위 20%":  [fmt_krw(55000000), fmt_krw(62000), "45.0%"],
            }
            st.dataframe(pd.DataFrame(bench), use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="lock-overlay">🔒 벤치마크 비교는 Pro 이상 플랜에서 이용 가능합니다</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# TAB 3: 인건비 분석
# ════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-header">👥 인건비 상세 분석 <span class="free-badge">FREE</span></div>', unsafe_allow_html=True)
    lab_df  = data.get("인건비", pd.DataFrame())
    stf_df  = data.get("직원현황", pd.DataFrame())

    if lab_df.empty:
        st.warning("인건비 데이터가 없습니다.")
    else:
        lab_info = analysis.get("labor", {})
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("연간 총 인건비", fmt_krw(lab_info.get("total",0)))
        c2.metric("월평균 인건비", fmt_krw(lab_info.get("monthly_avg",0)))
        c3.metric("인건비율", f"{lab_info.get('ratio_to_revenue',0):.1f}%",
                  "적정" if lab_info.get("ratio_to_revenue",0)<55 else "⚠️ 과다")
        c4.metric("인건비 점수", f"{lab_info.get('score',0):.0f}점",
                  color_score(lab_info.get("score",0)))

        st.markdown("#### 월별 인건비 내역")
        st.dataframe(apply_accounting_format(lab_df, exclude_cols=["월"]),
                     use_container_width=True, hide_index=True)

        num_cols = [c for c in lab_df.columns if c != "월"]
        if num_cols:
            fig = go.Figure()
            palette = ["#0d47a1","#1565c0","#1976d2","#1e88e5","#42a5f5","#90caf9"]
            for i, col_name in enumerate(num_cols):
                fig.add_bar(
                    x=lab_df["월"], y=lab_df[col_name],
                    name=col_name,
                    marker_color=palette[i % len(palette)],
                    hovertemplate=f"<b>%{{x}}</b><br>{col_name}: %{{customdata}}<extra></extra>",
                    customdata=[fmt_krw(v) for v in lab_df[col_name]])
            fig.update_layout(
                title="인건비 구성 추이", barmode="stack", height=300,
                legend=dict(orientation="h", y=-0.2),
                yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig, use_container_width=True)

        # 직원 현황
        if not stf_df.empty:
            st.markdown("#### 직원 구성 현황")
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(apply_accounting_format(stf_df, exclude_cols=["직종","인원수"]),
                             use_container_width=True, hide_index=True)
            with col2:
                if "인원수" in stf_df.columns and "직종" in stf_df.columns:
                    fig_stf = px.pie(stf_df, values="인원수", names="직종",
                                     title="직종별 인원 구성",
                                     color_discrete_sequence=px.colors.sequential.Blues_r)
                    fig_stf.update_layout(height=280)
                    st.plotly_chart(fig_stf, use_container_width=True)

        # 인건비율 기준 시각화
        ratio = lab_info.get("ratio_to_revenue", 0)
        st.markdown("#### 인건비율 평가 기준")
        gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=ratio,
            domain={'x':[0,1],'y':[0,1]},
            title={'text':"인건비율 (%)"},
            delta={'reference':50},
            gauge={
                'axis':{'range':[0,80]},
                'bar':{'color':"#1565c0"},
                'steps':[
                    {'range':[0,45],'color':'#c8e6c9'},
                    {'range':[45,55],'color':'#fff9c4'},
                    {'range':[55,65],'color':'#ffe0b2'},
                    {'range':[65,80],'color':'#ffcdd2'},
                ],
                'threshold':{'line':{'color':'red','width':3},'thickness':0.75,'value':55}
            }
        ))
        gauge.update_layout(height=250, margin=dict(l=20,r=20,t=40,b=0))
        st.plotly_chart(gauge, use_container_width=True)

# ════════════════════════════════════════════════════════
# TAB 4: 비용구조
# ════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-header">🏢 고정비 & 원가 분석 <span class="free-badge">FREE</span></div>', unsafe_allow_html=True)

    fix_df = data.get("고정비", pd.DataFrame())
    sup_df = data.get("소모품약제", pd.DataFrame())
    mkt_df = data.get("마케팅", pd.DataFrame())

    c1,c2,c3 = st.columns(3)
    c1.metric("연간 고정비", fmt_krw(analysis["fixed"]["total"]),
              f"매출대비 {analysis['fixed']['ratio_to_revenue']:.1f}%")
    c2.metric("연간 소모품/약제비", fmt_krw(analysis["supply"]["total"]),
              f"매출대비 {analysis['supply']['ratio_to_revenue']:.1f}%")
    c3.metric("연간 마케팅비", fmt_krw(analysis["marketing"]["total"]),
              f"매출대비 {analysis['marketing']['ratio_to_revenue']:.1f}%")

    col1, col2 = st.columns(2)
    with col1:
        if not fix_df.empty:
            st.markdown("#### 고정비 내역")
            st.dataframe(apply_accounting_format(fix_df, exclude_cols=["월"]),
                         use_container_width=True, hide_index=True)
            num_cols = [c for c in fix_df.columns if c != "월"]
            if num_cols:
                fig = go.Figure()
                palette = px.colors.sequential.Blues
                for i, col_name in enumerate(num_cols):
                    fig.add_scatter(
                        x=fix_df["월"], y=fix_df[col_name],
                        name=col_name, fill="tonexty" if i > 0 else "tozeroy",
                        line=dict(color=palette[min(i+2, len(palette)-1)]),
                        hovertemplate=f"<b>%{{x}}</b><br>{col_name}: %{{customdata}}<extra></extra>",
                        customdata=[fmt_krw(v) for v in fix_df[col_name]])
                fig.update_layout(
                    title="고정비 추이", height=280,
                    legend=dict(orientation="h", y=-0.3),
                    yaxis=dict(tickformat=",.0f"))
                st.plotly_chart(fig, use_container_width=True)
    with col2:
        if not sup_df.empty:
            st.markdown("#### 소모품/약제 내역")
            st.dataframe(apply_accounting_format(sup_df, exclude_cols=["월"]),
                         use_container_width=True, hide_index=True)
            num_cols = [c for c in sup_df.columns if c != "월"]
            if num_cols:
                fig2 = go.Figure()
                palette2 = px.colors.sequential.Oranges
                for i, col_name in enumerate(num_cols):
                    fig2.add_bar(
                        x=sup_df["월"], y=sup_df[col_name],
                        name=col_name,
                        marker_color=palette2[min(i+2, len(palette2)-1)],
                        hovertemplate=f"<b>%{{x}}</b><br>{col_name}: %{{customdata}}<extra></extra>",
                        customdata=[fmt_krw(v) for v in sup_df[col_name]])
                fig2.update_layout(
                    title="소모품/약제비 추이", barmode="stack", height=280,
                    legend=dict(orientation="h", y=-0.3),
                    yaxis=dict(tickformat=",.0f"))
                st.plotly_chart(fig2, use_container_width=True)

    if not mkt_df.empty:
        st.markdown("#### 마케팅 비용 내역")
        num_cols = [c for c in mkt_df.columns if c != "월"]
        if num_cols:
            fig3 = go.Figure()
            palette3 = px.colors.sequential.Greens
            for i, col_name in enumerate(num_cols):
                fig3.add_bar(
                    x=mkt_df["월"], y=mkt_df[col_name],
                    name=col_name,
                    marker_color=palette3[min(i+2, len(palette3)-1)],
                    hovertemplate=f"<b>%{{x}}</b><br>{col_name}: %{{customdata}}<extra></extra>",
                    customdata=[fmt_krw(v) for v in mkt_df[col_name]])
            fig3.update_layout(
                title="마케팅 비용 추이", barmode="stack", height=250,
                legend=dict(orientation="h", y=-0.3),
                yaxis=dict(tickformat=",.0f"))
            st.plotly_chart(fig3, use_container_width=True)

    if plan in ("pro","premium"):
        st.markdown('<div class="section-header">🔍 비용 절감 기회 분석 <span class="pro-badge">PRO</span></div>', unsafe_allow_html=True)
        fix_ratio = analysis["fixed"]["ratio_to_revenue"]
        sup_ratio = analysis["supply"]["ratio_to_revenue"]
        data_rows = []
        if fix_ratio > 20:
            saving = analysis["revenue"]["total"] * (fix_ratio - 18) / 100
            data_rows.append({
                "항목": "고정비", "현재비율": f"{fix_ratio:.1f}%", "업종평균": "18.0%",
                "절감목표": "18.0%", "예상절감액": fmt_krw(saving), "우선순위": "⭐⭐⭐"})
        if sup_ratio > 12:
            saving2 = analysis["revenue"]["total"] * (sup_ratio - 10) / 100
            data_rows.append({
                "항목": "소모품/약제비", "현재비율": f"{sup_ratio:.1f}%", "업종평균": "10.0%",
                "절감목표": "10.0%", "예상절감액": fmt_krw(saving2), "우선순위": "⭐⭐"})
        if data_rows:
            st.dataframe(pd.DataFrame(data_rows), use_container_width=True, hide_index=True)
        else:
            st.success("✅ 비용 구조가 업종 평균 대비 양호한 수준입니다.")
    else:
        st.markdown('<div class="lock-overlay">🔒 비용 절감 기회 분석은 Pro 이상 플랜에서 이용 가능합니다</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# TAB 5: 원무분석
# ════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-header">🏥 원무 상세 분석 <span class="free-badge">FREE</span></div>', unsafe_allow_html=True)
    out_df = data.get("원무", pd.DataFrame())

    if out_df.empty:
        st.warning("원무 데이터가 없습니다.")
    else:
        out_info = analysis.get("outpatient",{})
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("연간 총 내원환자", f"{out_info.get('total_patients',0):,}명")
        c2.metric("월평균 신환", f"{out_info.get('monthly_new',0):.0f}명")
        c3.metric("신환 비율", f"{out_info.get('new_patient_ratio',0):.1f}%")
        c4.metric("1인당 평균내원횟수", f"{out_info.get('avg_visits',0):.2f}회")

        st.dataframe(out_df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            if "총내원환자수" in out_df.columns and "신환수" in out_df.columns:
                out_df["재진수"] = out_df["총내원환자수"] - out_df["신환수"]
                fig = px.bar(out_df, x="월", y=["신환수","재진수"],
                             barmode="stack", title="신환/재진 구성",
                             color_discrete_map={"신환수":"#1565c0","재진수":"#90caf9"})
                fig.update_layout(height=300, legend=dict(orientation="h",y=-0.2))
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            if "1인당평균내원횟수" in out_df.columns:
                fig2 = px.line(out_df, x="월", y="1인당평균내원횟수",
                               title="1인당 평균 내원횟수 추이", markers=True)
                fig2.add_hline(y=out_df["1인당평균내원횟수"].mean(),
                               line_dash="dash", line_color="red",
                               annotation_text="평균")
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)

        # 주상병 현황
        if "주상병1" in out_df.columns:
            st.markdown("#### 주요 상병 현황")
            disease_count = out_df["주상병1"].value_counts().reset_index()
            disease_count.columns = ["상병명","월수"]
            if "주상병2" in out_df.columns:
                d2 = out_df["주상병2"].value_counts().reset_index()
                d2.columns = ["상병명","월수"]
                disease_count = pd.concat([disease_count, d2]).groupby("상병명").sum().reset_index()
            fig3 = px.bar(disease_count.sort_values("월수",ascending=True),
                          x="월수", y="상병명", orientation="h",
                          title="주요 상병 빈도", color="월수",
                          color_continuous_scale="Blues")
            fig3.update_layout(height=280)
            st.plotly_chart(fig3, use_container_width=True)

# ════════════════════════════════════════════════════════
# TAB 6: 수익성 분석
# ════════════════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="section-header">📈 수익성 심층 분석 <span class="free-badge">FREE</span></div>', unsafe_allow_html=True)

    pro_info = analysis.get("profitability",{})
    rev_info = analysis.get("revenue",{})
    c1,c2,c3 = st.columns(3)
    c1.metric("영업이익", fmt_krw(pro_info.get("op_profit",0)))
    c2.metric("영업이익률", f"{pro_info.get('op_margin',0):.1f}%",
              "우수" if pro_info.get("op_margin",0)>15 else ("양호" if pro_info.get("op_margin",0)>8 else "⚠️ 개선필요"))
    c3.metric("수익성 점수", f"{pro_info.get('score',0):.0f}점 / 100점",
              color_score(pro_info.get("score",0)))

    # 손익 계산서 요약
    rev_total  = rev_info.get("total", 0)
    lab_total  = analysis["labor"]["total"]
    fix_total  = analysis["fixed"]["total"]
    sup_total  = analysis["supply"]["total"]
    mkt_total  = analysis["marketing"]["total"]
    cost_total = lab_total + fix_total + sup_total + mkt_total
    op_profit  = rev_total - cost_total

    pnl = pd.DataFrame({
        "항목": ["📈 의료수익 (매출)", "  └ 인건비", "  └ 고정비",
                 "  └ 소모품/약제비", "  └ 마케팅비", "💰 영업이익"],
        "금액": [rev_total, -lab_total, -fix_total, -sup_total, -mkt_total, op_profit],
        "비율(%)": [100,
                    -lab_total/rev_total*100 if rev_total else 0,
                    -fix_total/rev_total*100 if rev_total else 0,
                    -sup_total/rev_total*100 if rev_total else 0,
                    -mkt_total/rev_total*100 if rev_total else 0,
                    op_profit/rev_total*100 if rev_total else 0]
    })
    # 회계서식: 양수 X,XXX / 음수 (X,XXX) / 비율 괄호 표기
    pnl["금액(회계)"] = pnl["금액"].apply(fmt_krw)
    pnl["비율(%)"]   = pnl["비율(%)"].apply(lambda x: f"({abs(x):.1f}%)" if x < 0 else f"{x:.1f}%")
    st.markdown("#### 손익 구조 요약")
    st.dataframe(pnl[["항목","금액(회계)","비율(%)"]], use_container_width=True, hide_index=True)

    # 손익 폭포수 차트
    fig_wf = go.Figure(go.Waterfall(
        name="손익",
        orientation="v",
        measure=["absolute","relative","relative","relative","relative","total"],
        x=["매출","인건비","고정비","소모품/약제","마케팅비","영업이익"],
        textposition="outside",
        text=[fmt_krw(v) for v in [rev_total,-lab_total,-fix_total,-sup_total,-mkt_total,op_profit]],
        y=[rev_total,-lab_total,-fix_total,-sup_total,-mkt_total,op_profit],
        connector={"line":{"color":"rgb(63,63,63)"}},
        increasing={"marker":{"color":"#1565c0"}},
        decreasing={"marker":{"color":"#c62828"}},
        totals={"marker":{"color":"#2e7d32"}},
        hovertemplate="<b>%{x}</b><br>금액: %{text}<extra></extra>"
    ))
    fig_wf.update_layout(
        title="손익 폭포수 차트", height=380,
        margin=dict(l=0,r=0,t=40,b=0),
        yaxis=dict(tickformat=",.0f"))
    st.plotly_chart(fig_wf, use_container_width=True)

    if plan in ("pro","premium"):
        st.markdown('<div class="section-header">📊 수익 개선 시뮬레이션 <span class="pro-badge">PRO</span></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 📉 비용 절감 시나리오")
            lab_reduce  = st.slider("인건비 절감(%)", 0, 20, 5)
            fix_reduce  = st.slider("고정비 절감(%)", 0, 20, 5)
            sup_reduce  = st.slider("소모품 절감(%)", 0, 20, 5)
        with col2:
            st.markdown("##### 📈 매출 증가 시나리오")
            rev_increase = st.slider("매출 증가(%)", 0, 50, 10)
            new_pt_add   = st.slider("신환 추가(명/월)", 0, 50, 10)

        new_lab    = lab_total * (1 - lab_reduce/100)
        new_fix    = fix_total * (1 - fix_reduce/100)
        new_sup    = sup_total * (1 - sup_reduce/100)
        new_rev    = rev_total * (1 + rev_increase/100)
        avg_pres   = rev_info.get("avg_prescription", 50000)
        new_rev   += new_pt_add * 12 * avg_pres
        new_cost   = new_lab + new_fix + new_sup + mkt_total
        new_profit = new_rev - new_cost
        new_margin = new_profit / new_rev * 100 if new_rev else 0

        st.markdown("---")
        sc1,sc2,sc3 = st.columns(3)
        sc1.metric("예상 연간 매출",  fmt_krw(new_rev),    f"{(new_rev-rev_total)/rev_total*100:+.1f}%")
        sc2.metric("예상 영업이익",   fmt_krw(new_profit),  f"{(new_profit-op_profit)/max(abs(op_profit),1)*100:+.1f}%")
        sc3.metric("예상 영업이익률", f"{new_margin:.1f}%", f"{new_margin-pro_info.get('op_margin',0):+.1f}%p")
    else:
        st.markdown('<div class="lock-overlay">🔒 수익 개선 시뮬레이션은 Pro 이상 플랜에서 이용 가능합니다</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# TAB 7: AI 진단
# ════════════════════════════════════════════════════════
with tabs[6]:
    st.markdown('<div class="section-header">🤖 AI 멀티엔진 진단 <span class="pro-badge">PRO+</span></div>', unsafe_allow_html=True)

    if plan == "free":
        st.markdown("""
        <div class="lock-overlay">
        <h3>🔒 AI 진단은 유료 플랜 전용 기능입니다</h3>
        <p>Pro 또는 Premium 플랜으로 업그레이드하여 Claude, GPT-4o, Gemini AI의 전문적인 병원 경영 진단을 받아보세요.</p>
        <br>
        <b>AI 진단 제공 내용:</b><br>
        ✅ 수익구조 심층 분석 | ✅ 비용 절감 방안 | ✅ 환자 관리 전략<br>
        ✅ 리스크 진단 | ✅ 전략적 로드맵 | ✅ 벤치마크 비교
        </div>
        """, unsafe_allow_html=True)
    else:
        ai_prompt = build_ai_prompt(
            st.session_state.hospital_name,
            analysis,
            data
        )

        available_ais = []
        if plan in ("pro","premium"):
            available_ais = ["Claude (Anthropic)", "GPT-4o (OpenAI)"]
        if plan == "premium":
            available_ais.append("Gemini 1.5 Pro (Google)")

        st.markdown(f"**사용 가능한 AI:** {', '.join(available_ais)}")
        st.markdown("---")

        # Claude
        st.markdown("### 🟣 Claude (Anthropic) 진단")
        api_key_claude = st.session_state.api_keys.get("claude","")
        if api_key_claude:
            if st.button("Claude로 진단 실행", key="btn_claude"):
                with st.spinner("Claude가 분석 중입니다... (1~2분 소요)"):
                    result = call_claude(api_key_claude, ai_prompt)
                    st.session_state.ai_results["claude"] = result
            if "claude" in st.session_state.ai_results:
                st.markdown(f'<div class="ai-response">{st.session_state.ai_results["claude"]}</div>', unsafe_allow_html=True)
        else:
            st.info("사이드바에서 Claude API Key를 입력해 주세요.")

        st.markdown("---")

        # GPT-4o
        st.markdown("### 🟢 GPT-4o (OpenAI) 진단")
        api_key_openai = st.session_state.api_keys.get("openai","")
        if api_key_openai:
            if st.button("GPT-4o로 진단 실행", key="btn_openai"):
                with st.spinner("GPT-4o가 분석 중입니다... (1~2분 소요)"):
                    result = call_openai(api_key_openai, ai_prompt)
                    st.session_state.ai_results["openai"] = result
            if "openai" in st.session_state.ai_results:
                st.markdown(f'<div class="ai-response">{st.session_state.ai_results["openai"]}</div>', unsafe_allow_html=True)
        else:
            st.info("사이드바에서 OpenAI API Key를 입력해 주세요.")

        # Gemini (Premium only)
        if plan == "premium":
            st.markdown("---")
            st.markdown("### 🔵 Gemini 1.5 Pro (Google) 진단 <span class='premium-badge'>PREMIUM</span>", unsafe_allow_html=True)
            api_key_gemini = st.session_state.api_keys.get("gemini","")
            if api_key_gemini:
                if st.button("Gemini로 진단 실행", key="btn_gemini"):
                    with st.spinner("Gemini가 분석 중입니다... (1~2분 소요)"):
                        result = call_gemini(api_key_gemini, ai_prompt)
                        st.session_state.ai_results["gemini"] = result
                if "gemini" in st.session_state.ai_results:
                    st.markdown(f'<div class="ai-response">{st.session_state.ai_results["gemini"]}</div>', unsafe_allow_html=True)
            else:
                st.info("사이드바에서 Gemini API Key를 입력해 주세요.")

            # AI 통합 의견 (Premium)
            if len(st.session_state.ai_results) >= 2:
                st.markdown("---")
                st.markdown("### 🌟 AI 통합 종합 의견 <span class='premium-badge'>PREMIUM</span>", unsafe_allow_html=True)
                if st.button("AI 통합 의견 생성", key="btn_integrate"):
                    ai_summaries = "\n\n".join([
                        f"[{k.upper()} 진단 요약]:\n{v[:800]}..."
                        for k,v in st.session_state.ai_results.items()
                    ])
                    integrate_prompt = f"""
다음은 3개 AI의 병원 경영 진단 결과입니다. 각 AI의 공통점과 차이점을 분석하고,
가장 중요한 핵심 과제 5가지와 우선순위 액션플랜을 도출해 주세요.

{ai_summaries}

결론은 간결하고 실행 가능한 형태로 작성해 주세요.
"""
                    if api_key_claude:
                        with st.spinner("통합 의견 생성 중..."):
                            integrated = call_claude(api_key_claude, integrate_prompt)
                            st.session_state.ai_results["integrated"] = integrated
                if "integrated" in st.session_state.ai_results:
                    st.markdown(f'<div class="report-box">{st.session_state.ai_results["integrated"]}</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# TAB 8: 종합 보고서
# ════════════════════════════════════════════════════════
with tabs[7]:
    st.markdown('<div class="section-header">📋 종합 경영진단 보고서</div>', unsafe_allow_html=True)

    now = datetime.now().strftime("%Y년 %m월 %d일")
    rev_info = analysis.get("revenue",{})
    lab_info = analysis.get("labor",{})
    fix_info = analysis.get("fixed",{})
    sup_info = analysis.get("supply",{})
    out_info = analysis.get("outpatient",{})
    pro_info = analysis.get("profitability",{})
    ovr_info = analysis.get("overall",{})

    st.markdown(f"""
    <div class="report-box">
    <h2 style="text-align:center;color:#1a237e">병원 경영진단 보고서</h2>
    <p style="text-align:center;color:#555">진단일: {now} | 병원명: {st.session_state.hospital_name}</p>
    <hr>

    <h3>1. 경영 현황 요약</h3>
    <table width="100%" style="border-collapse:collapse;font-size:0.9rem">
    <tr style="background:#e3f2fd"><th style="padding:6px;border:1px solid #ccc">구분</th><th style="padding:6px;border:1px solid #ccc">지표</th><th style="padding:6px;border:1px solid #ccc;text-align:right">수치</th><th style="padding:6px;border:1px solid #ccc">평가</th></tr>
    <tr>
      <td style="padding:6px;border:1px solid #eee">매출</td>
      <td style="padding:6px;border:1px solid #eee">연간 총매출</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right;font-family:monospace"><b>{fmt_krw(rev_info.get('total',0))}</b></td>
      <td style="padding:6px;border:1px solid #eee">{'🟢 양호' if rev_info.get('growth_rate',0)>0 else '🔴 감소'}</td>
    </tr>
    <tr style="background:#f5f5f5">
      <td style="padding:6px;border:1px solid #eee">매출</td>
      <td style="padding:6px;border:1px solid #eee">매출 성장률</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right">{rev_info.get('growth_rate',0):+.1f}%</td>
      <td style="padding:6px;border:1px solid #eee">{'🟢' if rev_info.get('growth_rate',0)>5 else '🟡' if rev_info.get('growth_rate',0)>0 else '🔴'}</td>
    </tr>
    <tr>
      <td style="padding:6px;border:1px solid #eee">매출</td>
      <td style="padding:6px;border:1px solid #eee">월평균 매출</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right;font-family:monospace">{fmt_krw(rev_info.get('monthly_avg',0))}</td>
      <td style="padding:6px;border:1px solid #eee">—</td>
    </tr>
    <tr style="background:#f5f5f5">
      <td style="padding:6px;border:1px solid #eee">매출</td>
      <td style="padding:6px;border:1px solid #eee">1인당 평균처방금액</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right;font-family:monospace">{fmt_krw(rev_info.get('avg_prescription',0))}</td>
      <td style="padding:6px;border:1px solid #eee">—</td>
    </tr>
    <tr>
      <td style="padding:6px;border:1px solid #eee">인건비</td>
      <td style="padding:6px;border:1px solid #eee">연간 인건비</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right;font-family:monospace">{fmt_krw(lab_info.get('total',0))}</td>
      <td style="padding:6px;border:1px solid #eee">인건비율 {lab_info.get('ratio_to_revenue',0):.1f}%<br>{'🟢 적정' if lab_info.get('ratio_to_revenue',0)<50 else '🟡 주의' if lab_info.get('ratio_to_revenue',0)<60 else '🔴 과다'}</td>
    </tr>
    <tr style="background:#f5f5f5">
      <td style="padding:6px;border:1px solid #eee">고정비</td>
      <td style="padding:6px;border:1px solid #eee">연간 고정비</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right;font-family:monospace">{fmt_krw(fix_info.get('total',0))}</td>
      <td style="padding:6px;border:1px solid #eee">고정비율 {fix_info.get('ratio_to_revenue',0):.1f}%<br>{'🟢 적정' if fix_info.get('ratio_to_revenue',0)<20 else '🟡 주의' if fix_info.get('ratio_to_revenue',0)<25 else '🔴 과다'}</td>
    </tr>
    <tr>
      <td style="padding:6px;border:1px solid #eee">원가</td>
      <td style="padding:6px;border:1px solid #eee">소모품/약제비율</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right">{sup_info.get('ratio_to_revenue',0):.1f}%</td>
      <td style="padding:6px;border:1px solid #eee">{'🟢 적정' if sup_info.get('ratio_to_revenue',0)<12 else '🟡 주의' if sup_info.get('ratio_to_revenue',0)<18 else '🔴 과다'}</td>
    </tr>
    <tr style="background:#f5f5f5">
      <td style="padding:6px;border:1px solid #eee">수익성</td>
      <td style="padding:6px;border:1px solid #eee">영업이익</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right;font-family:monospace">{fmt_krw(pro_info.get('op_profit',0))}</td>
      <td style="padding:6px;border:1px solid #eee">이익률 {pro_info.get('op_margin',0):.1f}%<br>{'🟢 우수' if pro_info.get('op_margin',0)>15 else '🟡 양호' if pro_info.get('op_margin',0)>8 else '🔴 개선필요'}</td>
    </tr>
    <tr>
      <td style="padding:6px;border:1px solid #eee">환자</td>
      <td style="padding:6px;border:1px solid #eee">신환비율</td>
      <td style="padding:6px;border:1px solid #eee;text-align:right">{out_info.get('new_patient_ratio',0):.1f}%</td>
      <td style="padding:6px;border:1px solid #eee">{'🟢 우수' if out_info.get('new_patient_ratio',0)>12 else '🟡 보통' if out_info.get('new_patient_ratio',0)>7 else '🔴 저조'}</td>
    </tr>
    <tr style="background:#e8f5e9">
      <td colspan="2" style="padding:6px;border:1px solid #ccc"><b>종합 경영점수</b></td>
      <td colspan="2" style="padding:6px;border:1px solid #ccc;text-align:center"><b>{color_score(ovr_info.get('score',0))} {ovr_info.get('score',0):.0f} / 100점</b></td>
    </tr>
    </table>

    <h3 style="margin-top:1.5rem">2. 주요 개선 과제</h3>
    </div>
    """, unsafe_allow_html=True)

    # 개선 과제 도출
    issues = []
    lab_r = lab_info.get("ratio_to_revenue",0)
    fix_r = fix_info.get("ratio_to_revenue",0)
    sup_r = sup_info.get("ratio_to_revenue",0)
    new_r = out_info.get("new_patient_ratio",0)
    mgn   = pro_info.get("op_margin",0)

    if lab_r > 55:
        issues.append(("🔴 긴급","인건비 과다","인건비율이 업종 권고 기준(55%)을 초과하였습니다.","직종별 업무 효율화, 인센티브 구조 조정, 정원 재검토 필요"))
    if mgn < 8:
        issues.append(("🔴 긴급","영업이익률 저조","영업이익률이 업종 평균(8~12%)을 하회합니다.","수익 구조 전반 재검토 및 비급여 항목 확대 검토"))
    if fix_r > 22:
        issues.append(("🟡 주의","고정비 과다","고정비율이 권고 수준(20%)을 초과합니다.","임차료 재협상, 렌탈 재검토, 에너지 절감 방안 수립"))
    if sup_r > 15:
        issues.append(("🟡 주의","소모품/약제비 과다","소모품·약제 비용이 권고 수준(12%)을 초과합니다.","공동구매, 재고관리 시스템 도입, 처방 패턴 분석"))
    if new_r < 8:
        issues.append(("🟡 주의","신환 유입 부족","신환 비율이 낮아 환자 기반 확대가 필요합니다.","온라인 마케팅 강화, 지역사회 연계, 소개 프로그램 운영"))
    if not issues:
        issues.append(("🟢 양호","전반적 경영 지표 양호","대부분의 경영 지표가 업종 평균 수준 이상입니다.","현재 수준 유지 및 상위 20% 달성을 위한 성장 전략 수립"))

    for priority, title, desc, action in issues:
        color = "#ffebee" if "긴급" in priority else ("#fff3e0" if "주의" in priority else "#e8f5e9")
        st.markdown(f"""
        <div style="background:{color};border-radius:8px;padding:1rem;margin:0.5rem 0">
        <b>{priority} | {title}</b><br>
        <span style="color:#555">{desc}</span><br>
        <span style="color:#1565c0">💡 대응방안: {action}</span>
        </div>
        """, unsafe_allow_html=True)

    if plan in ("pro","premium"):
        st.markdown('<div class="section-header">🗺️ 전략 로드맵 <span class="pro-badge">PRO</span></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="report-box">
        <h4>📅 단계별 전략 과제</h4>
        <table width="100%" style="border-collapse:collapse;font-size:0.88rem">
        <tr style="background:#1565c0;color:white">
            <th style="padding:8px">기간</th><th>핵심 과제</th><th>세부 실행 사항</th><th>기대 효과</th>
        </tr>
        <tr style="background:#e3f2fd">
            <td><b>즉시~1개월</b></td>
            <td>비용 현황 정밀 진단</td>
            <td>① 인건비 항목별 상세 분석<br>② 불필요 고정비 파악<br>③ 약제·소모품 재고 실사</td>
            <td>과다 비용 항목 20% 파악</td>
        </tr>
        <tr>
            <td><b>1~3개월</b></td>
            <td>비용 구조 최적화</td>
            <td>① 임차료·렌탈 재협상<br>② 공동구매 네트워크 참여<br>③ 인센티브 구조 재설계</td>
            <td>고정비 10~15% 절감</td>
        </tr>
        <tr style="background:#e3f2fd">
            <td><b>3~6개월</b></td>
            <td>수익 다각화</td>
            <td>① 비급여 항목 발굴·확대<br>② 건강검진 패키지 개발<br>③ 지역사회 협력 강화</td>
            <td>비급여 매출 30% 증가</td>
        </tr>
        <tr>
            <td><b>6~12개월</b></td>
            <td>환자 기반 확대</td>
            <td>① 디지털 마케팅 체계화<br>② 환자 만족도 관리 강화<br>③ 예약·수납 시스템 개선</td>
            <td>신환 월 20명 이상 증가</td>
        </tr>
        <tr style="background:#e3f2fd">
            <td><b>1~3년</b></td>
            <td>지속 성장 기반 구축</td>
            <td>① EMR 데이터 기반 경영<br>② 의료진 역량 강화<br>③ 브랜드 포지셔닝 확립</td>
            <td>영업이익률 15% 이상 달성</td>
        </tr>
        </table>
        </div>
        """, unsafe_allow_html=True)

        # PDF 다운로드 (Premium)
        if plan == "premium":
            st.markdown('<div class="section-header">📄 보고서 출력 <span class="premium-badge">PREMIUM</span></div>', unsafe_allow_html=True)
            if st.button("📥 PDF 보고서 생성 (준비 중)", disabled=True):
                pass
            st.caption("PDF 출력 기능은 추후 업데이트 예정입니다. 현재는 브라우저 인쇄 기능(Ctrl+P)을 이용해 주세요.")

            # Excel 다운로드
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                for sheet_name, df in data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                summary = pd.DataFrame({
                    "지표": ["연간총매출","월평균매출","연간영업이익","영업이익률","인건비율","고정비율","신환비율","종합점수"],
                    "값":   [fmt_krw(rev_info.get("total",0)),
                             fmt_krw(rev_info.get("monthly_avg",0)),
                             fmt_krw(pro_info.get("op_profit",0)),
                             f"{pro_info.get('op_margin',0):.1f}%",
                             f"{lab_info.get('ratio_to_revenue',0):.1f}%",
                             f"{fix_info.get('ratio_to_revenue',0):.1f}%",
                             f"{out_info.get('new_patient_ratio',0):.1f}%",
                             f"{ovr_info.get('score',0):.0f}/100"]
                })
                summary.to_excel(writer, sheet_name="진단요약", index=False)
            st.download_button(
                label="📊 Excel 분석 데이터 다운로드",
                data=buf.getvalue(),
                file_name=f"병원경영진단_{st.session_state.hospital_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.markdown('<div class="lock-overlay">🔒 전략 로드맵 및 보고서 출력은 Pro 이상 플랜에서 이용 가능합니다</div>', unsafe_allow_html=True)

# ── 푸터 ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center;color:#aaa;font-size:0.8rem;padding:1rem">
🏥 병원 경영진단 시스템 v1.0 | Hospital Management Diagnosis Platform<br>
본 시스템의 진단 결과는 참고용이며, 최종 경영 결정은 전문 컨설턴트와 상담하시기 바랍니다.<br>
API 키는 세션 내에서만 사용되며 서버에 저장되지 않습니다.
</div>
""", unsafe_allow_html=True)
