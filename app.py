"""
授業・課題・バイトをまとめるスケジュール帳
実行方法:  streamlit run app.py
"""
import os
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------
# 設定
# ---------------------------------------------------------------
DATA_FILE = "schedule.csv"          # 予定を保存するファイル
TZ = ZoneInfo("Asia/Tokyo")         # 日本時間で計算する（公開サーバーは海外時間のため）
COLUMNS = ["id", "kind", "name", "date", "start", "end", "done"]

# 種類ごとの色（文字色, 背景色）
COLORS = {
    "授業": ("#1F4F85", "#E3EDF8"),
    "課題": ("#8F4410", "#FBE9DC"),
    "バイト": ("#1D5E4F", "#DDF0EA"),
}

# ワンタップで追加できるテンプレート（種類, 名前, 開始, 終了）
TEMPLATES = [
    ("バイト", "アルバイト", "17:00", "22:00"),
    ("授業", "1限の授業", "09:00", "10:30"),
    ("課題", "課題の締切", "", "23:59"),
]

WEEKDAYS = "月火水木金土日"

# 時刻の選択肢（10分刻み＋23:59）… 手入力しなくていいように
TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in range(0, 60, 10)] + ["23:59"]


# ---------------------------------------------------------------
# データの読み書き
# ---------------------------------------------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(DATA_FILE, dtype=str).fillna("")
    df["done"] = df["done"] == "True"
    return df


def save_data(df):
    df.to_csv(DATA_FILE, index=False)


def add_event(kind, name, day, start, end):
    df = load_data()
    new_row = {
        "id": uuid.uuid4().hex[:8],
        "kind": kind,
        "name": name,
        "date": day.isoformat(),
        "start": start,
        "end": end,
        "done": False,
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_data(df)


def delete_event(event_id):
    df = load_data()
    save_data(df[df["id"] != event_id])


def set_done(event_id, done):
    df = load_data()
    df.loc[df["id"] == event_id, "done"] = done
    save_data(df)


# ---------------------------------------------------------------
# 計算用の関数
# ---------------------------------------------------------------
def now():
    return datetime.now(TZ).replace(tzinfo=None)


def sort_key(row):
    """並べ替え用の時刻。課題は締切時刻、それ以外は開始時刻を使う"""
    return row["date"] + " " + (row["start"] or row["end"])


def sorted_events(df):
    if df.empty:
        return df
    return df.assign(_key=df.apply(sort_key, axis=1)).sort_values("_key").drop(columns="_key")


def to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def find_overlaps(df, day, start, end):
    """同じ日で時間が重なる予定（授業・バイト）を探す"""
    if not start or not end:
        return []
    s1, e1 = to_minutes(start), to_minutes(end)
    result = []
    for _, row in df[df["date"] == day.isoformat()].iterrows():
        if not row["start"]:        # 締切だけの課題は対象外
            continue
        s2, e2 = to_minutes(row["start"]), to_minutes(row["end"])
        overlap = min(e1, e2) - max(s1, s2)
        if overlap > 0:
            result.append((row, overlap))
    return result


def date_label(iso):
    d = date.fromisoformat(iso)
    return f"{d.month}月{d.day}日（{WEEKDAYS[d.weekday()]}）"


def badge(kind):
    fg, bg = COLORS[kind]
    return (f'<span style="background:{bg};color:{fg};font-size:12px;font-weight:700;'
            f'padding:2px 10px;border-radius:999px;">{kind}</span>')


def time_text(row):
    if row["start"]:
        return f'{row["start"]}〜{row["end"]}'
    return f'{row["end"]} 締切'


# ---------------------------------------------------------------
# 画面全体の見た目
# ---------------------------------------------------------------
st.set_page_config(page_title="スケジュール帳", page_icon="🗓", layout="centered")
st.markdown("""
<style>
.block-container {max-width: 480px; padding-top: 2rem;}
.card {background:#FFFFFF;border:1px solid #E4E0D7;border-radius:12px;padding:12px 14px;margin-bottom:8px;}
.next {background:#1F2328;color:#FFFFFF;border-radius:16px;padding:16px 18px;margin-bottom:16px;
       display:flex;justify-content:space-between;align-items:center;}
.muted {color:#5B6068;font-size:13px;}
.stButton button {min-height:48px;}
</style>
""", unsafe_allow_html=True)

df = load_data()
current = now()
today = current.date()

tab_home, tab_add, tab_list = st.tabs(["🏠 ホーム", "➕ 追加", "📋 一覧"])

# ---------------------------------------------------------------
# ① ホーム
# ---------------------------------------------------------------
with tab_home:
    st.markdown(f'<div class="muted">{date_label(today.isoformat())}</div>', unsafe_allow_html=True)
    st.subheader("今日の予定")

    # --- 次の予定まであと何分 ---
    upcoming = []
    for _, row in df[~df["done"]].iterrows():
        t = datetime.fromisoformat(f'{row["date"]} {row["start"] or row["end"]}')
        if t > current:
            upcoming.append((t, row))
    if upcoming:
        t, row = min(upcoming, key=lambda x: x[0])
        mins = int((t - current).total_seconds() // 60)
        left = f"{mins}分" if mins < 60 else f"{mins // 60}時間{mins % 60}分"
        when = t.strftime("%H:%M") if t.date() == today else f'{t.month}/{t.day} {t.strftime("%H:%M")}'
        st.markdown(f"""
        <div class="next">
          <div><div style="font-size:13px;color:#C9CDD3;">次の予定</div>
               <div style="font-size:18px;font-weight:700;">{when} {row["name"]}</div></div>
          <div style="text-align:right;"><div style="font-size:13px;color:#C9CDD3;">あと</div>
               <div style="font-size:22px;font-weight:700;">{left}</div></div>
        </div>""", unsafe_allow_html=True)

    # --- 締切が近い課題（7日以内） ---
    st.markdown("**締切が近い課題**")
    tasks = df[(df["kind"] == "課題") & (~df["done"])]
    near = []
    for _, row in tasks.iterrows():
        days_left = (date.fromisoformat(row["date"]) - today).days
        if 0 <= days_left <= 7:
            near.append((days_left, row))
    if not near:
        st.caption("7日以内に締切の課題はありません")
    for days_left, row in sorted(near, key=lambda x: x[0]):
        if days_left <= 1:
            color, bg = "#FFFFFF", "#B3261E"      # 赤：今日・明日
        elif days_left <= 3:
            color, bg = "#8F4410", "#FBE9DC"      # オレンジ：3日以内
        else:
            color, bg = "#5B6068", "#EFECE5"      # グレー：それ以降
        label = "今日" if days_left == 0 else f"あと{days_left}日"
        st.markdown(f"""
        <div class="card" style="display:flex;justify-content:space-between;align-items:center;">
          <div><div style="font-weight:500;">{row["name"]}</div>
               <div class="muted">{date_label(row["date"])} {row["end"]} 締切</div></div>
          <span style="background:{bg};color:{color};font-weight:700;font-size:13px;
                padding:6px 10px;border-radius:999px;white-space:nowrap;">{label}</span>
        </div>""", unsafe_allow_html=True)

    # --- 今日のタイムライン ---
    st.markdown("**タイムライン**")
    todays = sorted_events(df[df["date"] == today.isoformat()])
    if todays.empty:
        st.caption("今日の予定はありません。「追加」タブから登録できます。")
    for _, row in todays.iterrows():
        fg, _ = COLORS[row["kind"]]
        faded = "opacity:0.45;text-decoration:line-through;" if row["done"] else ""
        st.markdown(f"""
        <div class="card" style="display:flex;gap:12px;align-items:center;border-left:6px solid {fg};{faded}">
          <div style="width:48px;font-weight:700;color:#5B6068;">{row["start"] or row["end"]}</div>
          <div><div style="font-weight:500;">{row["name"]}</div>
               <div class="muted">{time_text(row)}</div></div>
        </div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# ② 予定の追加
# ---------------------------------------------------------------
with tab_add:
    st.subheader("予定を追加")

    # --- テンプレート（ワンタップ） ---
    st.markdown("**よく使う予定（ワンタップで追加）**")
    tpl_day = st.date_input("どの日に追加する？", value=today, key="tpl_day")
    cols = st.columns(len(TEMPLATES))
    for col, (kind, name, start, end) in zip(cols, TEMPLATES):
        label = f"{name}\n{start + '〜' if start else ''}{end}"
        if col.button(label, key=f"tpl_{name}", use_container_width=True):
            overlaps = find_overlaps(df, tpl_day, start, end)
            add_event(kind, name, tpl_day, start, end)
            if overlaps:
                names = "、".join(r["name"] for r, _ in overlaps)
                st.session_state["msg"] = ("warning", f"追加しましたが、「{names}」と時間が重なっています")
            else:
                st.session_state["msg"] = ("success", f"{name} を追加しました")
            st.rerun()

    st.divider()

    # --- 自分で入力 ---
    st.markdown("**自分で入力する**")
    kind = st.radio("種類", ["授業", "課題", "バイト"], horizontal=True)
    name = st.text_input("予定名", placeholder="例：レポート提出")
    day = st.date_input("日付", value=today)

    if kind == "課題":
        start = ""
        end = st.selectbox("締切時刻", TIME_OPTIONS, index=TIME_OPTIONS.index("23:59"))
    else:
        c1, c2 = st.columns(2)
        start = c1.selectbox("開始", TIME_OPTIONS, index=TIME_OPTIONS.index("09:00"))
        end = c2.selectbox("終了", TIME_OPTIONS, index=TIME_OPTIONS.index("10:30"))

    # --- 入力チェックと重なり警告 ---
    can_add = True
    if start and to_minutes(start) >= to_minutes(end):
        st.error("終了時刻は開始時刻より後にしてください")
        can_add = False

    overlaps = find_overlaps(df, day, start, end) if can_add else []
    if overlaps:
        lines = "\n".join(f"- {r['kind']}「{r['name']}」{time_text(r)}（{m}分重なる）" for r, m in overlaps)
        st.error(f"⚠️ 時間が重なっています\n\n{lines}")
        can_add = st.checkbox("重なっていても登録する")

    if st.button("登録する", type="primary", use_container_width=True, disabled=not can_add):
        if not name.strip():
            st.warning("予定名を入力してください")
        else:
            add_event(kind, name.strip(), day, start, end)
            st.session_state["msg"] = ("success", f"{name} を登録しました")
            st.rerun()

# ---------------------------------------------------------------
# ③ 一覧（完了チェック・削除）
# ---------------------------------------------------------------
with tab_list:
    st.subheader("予定の一覧")
    show_past = st.toggle("過去の予定も表示", value=False)

    items = df if show_past else df[df["date"] >= today.isoformat()]
    items = sorted_events(items)
    if items.empty:
        st.caption("予定はまだありません")

    for day_iso, group in items.groupby("date", sort=True):
        st.markdown(f"**{date_label(day_iso)}{' 今日' if day_iso == today.isoformat() else ''}**")
        for _, row in group.iterrows():
            c1, c2, c3 = st.columns([1, 5, 1], vertical_alignment="center")
            with c1:
                if row["kind"] == "課題":
                    checked = st.checkbox("完了", value=row["done"], key=f"done_{row['id']}",
                                          label_visibility="collapsed")
                    if checked != row["done"]:
                        set_done(row["id"], checked)
                        st.rerun()
                else:
                    st.markdown(f'<span class="muted">{row["start"]}</span>', unsafe_allow_html=True)
            with c2:
                style = "color:#6B7078;text-decoration:line-through;" if row["done"] else ""
                st.markdown(f'{badge(row["kind"])} <span style="{style}">{row["name"]}</span>'
                            f'<br><span class="muted">{time_text(row)}</span>', unsafe_allow_html=True)
            with c3:
                if st.button("🗑", key=f"del_{row['id']}", help="削除"):
                    delete_event(row["id"])
                    st.rerun()

# 登録・削除後のメッセージ（画面が再読み込みされても1回だけ表示）
if "msg" in st.session_state:
    level, text = st.session_state.pop("msg")
    st.toast(text, icon="⚠️" if level == "warning" else "✅")
