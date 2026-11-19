"""
PS 47 - Daily Journal Summarizer
Raginee Chunkhare | Roll No 47 | LY-AIA-7 | MIT ADT University

Store dated journal entries in a CSV -> LLM (Groq) tags the mood of each entry
-> weekly summary with highlights + a line chart of mood.

Run:  streamlit run app.py
"""

import html
import os
import shutil
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from journal_llm import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    get_client,
    summarize_week,
    tag_entry,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent
JOURNAL_CSV = BASE_DIR / "journal.csv"
SAMPLE_CSV = BASE_DIR / "sample_journal.csv"
COLUMNS = ["date", "entry", "mood", "mood_score", "highlight", "reason"]

MOOD_EMOJI = {
    "Happy": "😊", "Excited": "🤩", "Motivated": "💪", "Calm": "😌", "Neutral": "😐",
    "Tired": "😴", "Anxious": "😟", "Stressed": "😣", "Sad": "😢", "Angry": "😠",
}

st.set_page_config(page_title="Daily Journal Summarizer", page_icon="📓", layout="wide")

# ------------------------------------------------------------------ theme --
# "Bullet journal" look: dotted paper, handwritten headings, lined writing page,
# sticky-note cards with washi tape. Colours: soft pink + lavender.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

html, body, .stApp, p, label, li, input, textarea, .stMarkdown { font-family: 'Lora', Georgia, serif !important; }
.stApp {
    background-color: #FFF4F9;
    background-image: radial-gradient(#E9C6DE 1.1px, transparent 1.1px);
    background-size: 22px 22px;
    color: #4A2C5E;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
    background-color: #F1E6FB;
    background-image: radial-gradient(#D9C3EE 1px, transparent 1px);
    background-size: 18px 18px;
    border-right: 2px dashed #D7B6E8;
}

/* handwritten headings */
h1, h2, h3, [data-testid="stSidebar"] h1 { font-family: 'Caveat', cursive !important; letter-spacing: .5px; }
h1 { color: #B5409F !important; font-size: 3.4rem !important; font-weight: 700 !important; }
h1 .hl { background: linear-gradient(transparent 62%, #F9C9E5 62%); padding: 0 6px; }
h2, h3 { color: #8A3FB8 !important; font-size: 2rem !important; font-weight: 700 !important; }

/* sticker buttons */
.stButton > button, .stDownloadButton > button {
    background: #F7B5DA; color: #4A2C5E !important; border: 2px solid #4A2C5E; border-radius: 12px;
    box-shadow: 3px 3px 0 #4A2C5E; font-family: 'Caveat', cursive !important; font-size: 1.35rem; padding: 0 18px;
}
.stButton > button p, .stDownloadButton > button p { font-family: 'Caveat', cursive !important; font-size: 1.35rem; }
.stButton > button:hover, .stDownloadButton > button:hover { background: #D9C2F5; color: #4A2C5E !important; border-color: #4A2C5E; }
.stButton > button:active { box-shadow: 1px 1px 0 #4A2C5E; transform: translate(2px, 2px); }

/* notebook index tabs */
.stTabs [role="tablist"] { gap: 6px; border-bottom: 2px solid #4A2C5E !important; }
.stTabs [role="tab"] { border: 2px solid #4A2C5E !important; border-bottom: none !important;
    border-radius: 12px 12px 0 0 !important; padding: 4px 18px !important; background: #FFE3F1 !important; }
.stTabs [role="tab"]:nth-child(2) { background: #EEDFFF !important; }
.stTabs [role="tab"]:nth-child(3) { background: #FFEBD9 !important; }
.stTabs [role="tab"] p { font-family: 'Caveat', cursive !important; font-size: 1.45rem !important; color: #4A2C5E !important; }
.stTabs [role="tab"][aria-selected="true"] { transform: translateY(-4px); box-shadow: 0 -2px 0 #4A2C5E inset; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

/* lined paper for writing */
textarea {
    background-color: #FFFDF8 !important;
    background-image: linear-gradient(90deg, transparent 38px, #F4A9CF 38px, #F4A9CF 40px, transparent 40px),
                      repeating-linear-gradient(#FFFDF8 0px, #FFFDF8 29px, #E2D3F2 29px, #E2D3F2 30px) !important;
    line-height: 30px !important; padding-left: 52px !important; font-size: 1.05rem !important;
    border: 2px solid #4A2C5E !important; border-radius: 6px !important;
}
input, [data-baseweb="select"] > div, [data-baseweb="input"] { border-radius: 10px !important; }

/* sticky-note stat cards with washi tape */
[data-testid="stMetric"] {
    position: relative; background: #FFF9C9; border: none; border-radius: 3px; padding: 22px 16px 14px;
    box-shadow: 2px 4px 10px rgba(74,44,94,.15); transform: rotate(-1.5deg);
}
[data-testid="stMetric"]::before {
    content: ""; position: absolute; top: -10px; left: 50%; width: 80px; height: 22px; margin-left: -40px;
    background: rgba(241,124,196,.55); transform: rotate(-3deg);
}
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"] { background: #FFE0EF; transform: rotate(1.2deg); }
[data-testid="stColumn"]:nth-child(2) [data-testid="stMetric"]::before { background: rgba(169,112,240,.45); }
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"] { background: #E8DDFF; transform: rotate(-0.8deg); }
[data-testid="stColumn"]:nth-child(3) [data-testid="stMetric"]::before { background: rgba(120,200,170,.5); }
[data-testid="stColumn"]:nth-child(4) [data-testid="stMetric"] { background: #DDF3EA; transform: rotate(1.6deg); }
[data-testid="stMetric"] label p { font-family: 'Caveat', cursive !important; font-size: 1.35rem !important; color: #6B4A7C !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { font-family: 'Caveat', cursive !important; color: #4A2C5E; font-size: 2.3rem !important; }

/* journal page card for the weekly summary */
.page { position: relative; background: #FFFDF8; border: 2px solid #4A2C5E; border-radius: 6px;
    padding: 30px 34px 22px; margin: 18px 0; box-shadow: 6px 6px 0 #E9C6DE; }
.page::before { content: ""; position: absolute; top: -12px; left: 30px; width: 110px; height: 24px;
    background: repeating-linear-gradient(45deg, rgba(241,124,196,.6) 0 8px, rgba(255,255,255,.6) 8px 16px); transform: rotate(-4deg); }
.page::after { content: ""; position: absolute; top: -12px; right: 30px; width: 90px; height: 24px;
    background: rgba(169,112,240,.45); transform: rotate(5deg); }
.page h4 { font-family: 'Caveat', cursive !important; color: #B5409F; font-size: 1.7rem; margin: 10px 0 2px; }
.page .big { font-family: 'Caveat', cursive !important; font-size: 2.2rem; color: #8A3FB8; margin: 0; }
.page .trend { background: linear-gradient(transparent 55%, #FBE0A8 55%); display: inline; font-style: italic; }
.page ul { margin-top: 2px; } .page li::marker { content: "✿  "; color: #F17CC4; }
.page .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 36px; }
.doodle, .doodle * { font-family: 'Caveat', cursive !important; color: #A970F0; font-size: 1.4rem; margin-top: -14px; }
[data-testid="stDataFrame"] { border: 2px solid #4A2C5E; border-radius: 6px; }
[data-testid="stExpander"] { background: #FFFDF8; border: 2px dashed #D7B6E8; border-radius: 8px; }
.stProgress > div > div > div > div { background: repeating-linear-gradient(45deg, #F17CC4 0 10px, #A970F0 10px 20px); }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------ CSV storage --

def load_journal() -> pd.DataFrame:
    if JOURNAL_CSV.exists():
        df = pd.read_csv(JOURNAL_CSV)
    else:
        df = pd.DataFrame(columns=COLUMNS)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["entry"] = df["entry"].fillna("").astype(str)
    df["mood_score"] = pd.to_numeric(df["mood_score"], errors="coerce")
    return df[COLUMNS].sort_values("date").reset_index(drop=True)


def save_journal(df: pd.DataFrame) -> None:
    out = df.copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(JOURNAL_CSV, index=False)


def week_start(d) -> pd.Timestamp:
    """Monday of the week the date falls in."""
    d = pd.Timestamp(d).normalize()
    return d - pd.Timedelta(days=d.weekday())


# --------------------------------------------------------------- API key --

def find_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("GROQ_API_KEY", "")
        except Exception:
            key = ""
    return key


# ---------------------------------------------------------------- sidebar --

st.sidebar.title("Settings")
api_key = find_api_key()
if api_key:
    st.sidebar.success("Groq API key loaded")
else:
    api_key = st.sidebar.text_input("Groq API key", type="password",
                                    help="Get a free key at console.groq.com/keys")

model = st.sidebar.selectbox("Model", AVAILABLE_MODELS,
                             index=AVAILABLE_MODELS.index(DEFAULT_MODEL))
custom_model = st.sidebar.text_input("…or type another Groq model id (optional)")
if custom_model.strip():
    model = custom_model.strip()

st.sidebar.divider()
st.sidebar.subheader("Data")
if st.sidebar.button("Load sample entries"):
    shutil.copy(SAMPLE_CSV, JOURNAL_CSV)
    st.sidebar.success("Sample journal loaded.")
    st.rerun()

uploaded = st.sidebar.file_uploader("Upload your own journal CSV (columns: date, entry)", type="csv")
if uploaded is not None and st.sidebar.button("Use uploaded CSV"):
    up = pd.read_csv(uploaded)
    if {"date", "entry"}.issubset(up.columns):
        up.to_csv(JOURNAL_CSV, index=False)
        st.sidebar.success("Uploaded journal saved.")
        st.rerun()
    else:
        st.sidebar.error("CSV must have 'date' and 'entry' columns.")

df = load_journal()
if not df.empty:
    st.sidebar.download_button("Download journal.csv", JOURNAL_CSV.read_bytes(),
                               file_name="journal.csv", mime="text/csv")

# ----------------------------------------------------------------- header --

st.markdown("<h1><span class=\"hl\">Daily Journal Summarizer</span></h1>", unsafe_allow_html=True)
st.markdown('<div class="doodle">✿ a little space to look back on your week ☾</div>', unsafe_allow_html=True)
st.caption("Write daily entries, tag the mood of each one with an LLM, and review your week.  "
           "PS 47 · Raginee Chunkhare · Roll No 47")

tab_write, tab_entries, tab_week = st.tabs(["Write entry", "My entries", "Weekly review"])

# ------------------------------------------------------------- tab: write --

with tab_write:
    st.subheader("dear diary…")
    entry_date = st.date_input("Date", value=date.today())
    entry_text = st.text_area("How was your day?", height=200,
                              placeholder="Today I woke up late, had my NLP lab, ...")
    if st.button("Save entry", type="primary"):
        if not entry_text.strip():
            st.warning("Please write something first.")
        else:
            ts = pd.Timestamp(entry_date)
            if (df["date"] == ts).any():
                # One entry per day: append to the existing entry and clear old tags
                idx = df.index[df["date"] == ts][0]
                df.at[idx, "entry"] = df.at[idx, "entry"] + " " + entry_text.strip()
                df.loc[idx, ["mood", "mood_score", "highlight", "reason"]] = None
                st.info("You already had an entry for this date — added this text to it.")
            else:
                new_row = {"date": ts, "entry": entry_text.strip(), "mood": None,
                           "mood_score": None, "highlight": None, "reason": None}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_journal(df.sort_values("date"))
            st.success(f"Saved entry for {entry_date.strftime('%d %b %Y')}")

# ----------------------------------------------------------- tab: entries --

with tab_entries:
    df = load_journal()
    st.subheader(f"all my entries ({len(df)})")
    if df.empty:
        st.info("No entries yet. Write one, or click **Load sample entries** in the sidebar.")
    else:
        show = df.copy()
        show["date"] = show["date"].dt.strftime("%a %d %b %Y")
        show["mood"] = show["mood"].apply(
            lambda m: f"{MOOD_EMOJI.get(m, '')} {m}" if isinstance(m, str) else "not tagged yet")
        show["highlight"] = show["highlight"].fillna("")
        st.dataframe(show[["date", "entry", "mood", "mood_score", "highlight"]],
                     width="stretch", hide_index=True,
                     column_config={
                         "date": st.column_config.TextColumn("Date", width="small"),
                         "entry": st.column_config.TextColumn("Entry", width="large"),
                         "mood": st.column_config.TextColumn("Mood", width="small"),
                         "mood_score": st.column_config.NumberColumn("Score", width="small"),
                         "highlight": st.column_config.TextColumn("Highlight", width="medium"),
                     })

        tagged = df.dropna(subset=["mood_score"])
        if len(tagged) >= 2:
            st.subheader("mood over time")
            chart = (alt.Chart(tagged).mark_line(point=alt.OverlayMarkDef(color="#E05BB0", size=60), color="#9B5DE5", strokeWidth=2.5)
                     .encode(x=alt.X("date:T", title="Date"),
                             y=alt.Y("mood_score:Q", title="Mood score",
                                     scale=alt.Scale(domain=[1, 10])),
                             tooltip=[alt.Tooltip("date:T"), "mood", "mood_score", "highlight"])
                     .properties(height=300))
            st.altair_chart(chart.configure_axis(labelFont="Lora", titleFont="Caveat", titleFontSize=18, gridColor="#F1DDEB").configure_view(stroke=None), width="stretch")

# -------------------------------------------------------------- tab: week --

with tab_week:
    df = load_journal()
    if df.empty:
        st.info("No entries yet. Add some entries first.")
        st.stop()

    df["week"] = df["date"].apply(week_start)
    weeks = sorted(df["week"].unique(), reverse=True)
    week_labels = {
        w: f"{pd.Timestamp(w).strftime('%d %b')} – "
           f"{(pd.Timestamp(w) + timedelta(days=6)).strftime('%d %b %Y')}"
        for w in weeks
    }
    chosen = st.selectbox("Choose a week", weeks, format_func=lambda w: week_labels[w])
    week_df = df[df["week"] == chosen].copy()
    st.write(f"**{len(week_df)} entries** in this week.")

    retag = st.checkbox("Re-tag moods even if already tagged", value=False)

    if st.button("Analyse this week", type="primary"):
        if not api_key:
            st.error("Add your Groq API key in the sidebar first.")
            st.stop()
        client = get_client(api_key)
        to_tag = week_df if retag else week_df[week_df["mood_score"].isna()]

        # Step 1: tag the mood of each entry (one LLM call per entry)
        if len(to_tag):
            bar = st.progress(0.0, text="Tagging moods…")
            for i, (idx, row) in enumerate(to_tag.iterrows(), start=1):
                try:
                    tags = tag_entry(client, model, row["date"].strftime("%Y-%m-%d"), row["entry"])
                    for k, v in tags.items():
                        df.at[idx, k] = v
                except Exception as err:
                    st.error(f"Could not tag {row['date'].date()}: {err}")
                bar.progress(i / len(to_tag), text=f"Tagged {i}/{len(to_tag)} entries")
            save_journal(df.drop(columns=["week"]))
            week_df = df[df["week"] == chosen].copy()

        # Step 2: weekly summary from the tagged entries
        tagged_week = week_df.dropna(subset=["mood_score"])
        if tagged_week.empty:
            st.error("No entries could be tagged — check your API key / model.")
            st.stop()
        with st.spinner("Writing your weekly summary…"):
            try:
                st.session_state[f"summary_{chosen}"] = summarize_week(client, model, tagged_week)
            except Exception as err:
                st.error(f"Summary failed: {err}")

    # ---------------- results ----------------
    week_df = load_journal()
    week_df["week"] = week_df["date"].apply(week_start)
    week_df = week_df[(week_df["week"] == chosen)].dropna(subset=["mood_score"])
    summary = st.session_state.get(f"summary_{chosen}")

    if not week_df.empty:
        best = week_df.loc[week_df["mood_score"].idxmax()]
        worst = week_df.loc[week_df["mood_score"].idxmin()]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Average mood", f"{week_df['mood_score'].mean():.1f} / 10")
        c2.metric("Most common mood", week_df["mood"].mode()[0])
        c3.metric(f"Best day ({int(best['mood_score'])}/10)", best["date"].strftime("%a %d %b"))
        c4.metric(f"Lowest day ({int(worst['mood_score'])}/10)", worst["date"].strftime("%a %d %b"))

        week_df = week_df.sort_values("date")
        week_df["day"] = week_df["date"].dt.strftime("%a %d")
        st.subheader("my mood this week")
        line = (alt.Chart(week_df).mark_line(point=alt.OverlayMarkDef(size=140, color="#F17CC4", stroke="#4A2C5E", strokeWidth=1.5), color="#A970F0", strokeWidth=3, strokeDash=[6, 4], interpolate="monotone")
                .encode(x=alt.X("day:O", title="Day", sort=None, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y("mood_score:Q", title="Mood score (1–10)",
                                scale=alt.Scale(domain=[1, 10])),
                        tooltip=[alt.Tooltip("date:T"), "mood", "mood_score", "highlight"]))
        labels = (alt.Chart(week_df).mark_text(dy=-18, color="#8A3FB8", font="Caveat", fontSize=17)
                  .encode(x=alt.X("day:O", sort=None), y="mood_score:Q", text="mood"))
        st.altair_chart((line + labels).properties(height=320).configure_axis(labelFont="Lora", titleFont="Caveat", titleFontSize=18, gridColor="#F1DDEB").configure_view(stroke=None), width="stretch")

    if summary:
        e = html.escape
        lis = lambda items: "".join(f"<li>{e(str(i))}</li>" for i in items)
        st.markdown(f"""
<div class="page">
  <p class="big">this week I felt… {e(str(summary.get('overall_mood', '')))}</p>
  <p>{e(summary.get('summary', ''))}</p>
  <p><b>Mood trend:</b> <span class="trend">{e(summary.get('mood_trend', ''))}</span></p>
  <div class="grid">
    <div><h4>highlights</h4><ul>{lis(summary['highlights'])}</ul>
         <h4>patterns I noticed</h4><ul>{lis(summary['patterns'])}</ul></div>
    <div><h4>challenges</h4><ul>{lis(summary['challenges'] or ['None this week'])}</ul>
         <h4>for next week</h4><p>{e(summary.get('suggestion', ''))}</p></div>
  </div>
</div>""", unsafe_allow_html=True)

        with st.expander("Mood tag for each day"):
            for _, r in week_df.sort_values("date").iterrows():
                st.markdown(f"**{r['date'].strftime('%a %d %b')}** — "
                            f"{MOOD_EMOJI.get(r['mood'], '')} {r['mood']} ({int(r['mood_score'])}/10): "
                            f"{r['reason']}")

        md = [f"# Weekly Journal Summary ({week_labels[chosen]})", "",
              f"**Overall mood:** {summary.get('overall_mood', '')}", "",
              summary.get("summary", ""), "", f"**Mood trend:** {summary.get('mood_trend', '')}", "",
              "## Highlights", *[f"- {h}" for h in summary["highlights"]], "",
              "## Challenges", *[f"- {c}" for c in summary["challenges"]], "",
              "## Patterns", *[f"- {p}" for p in summary["patterns"]], "",
              "## Suggestion", summary.get("suggestion", ""), "",
              "## Daily moods",
              *[f"- {r['date'].strftime('%a %d %b')}: {r['mood']} ({int(r['mood_score'])}/10)"
                for _, r in week_df.sort_values("date").iterrows()]]
        st.download_button("Download summary (.md)", "\n".join(md),
                           file_name=f"weekly_summary_{pd.Timestamp(chosen).date()}.md")
    elif week_df.empty:
        st.caption("Click **Analyse this week** to tag moods and generate the summary.")

st.divider()
st.caption("Note: this tool gives AI-generated reflections for self-awareness only — it is not "
           "a mental-health assessment. If you're struggling, please talk to someone you trust "
           "or a counsellor.")
