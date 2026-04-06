import streamlit as st
import os
import json
import random
import time
from datetime import date
from pathlib import Path
from PIL import Image
from openai import OpenAI

# =========================
# 画面設定
# =========================
st.set_page_config(page_title="AIタロット占い", page_icon="🔮")

# =========================
# 設定値
# =========================
DAILY_LIMIT = 3                # 1セッション内の1日あたり回数
COOLDOWN_SECONDS = 20          # 連打対策
MODEL_NAME = "gpt-4.1-mini"
MAX_OUTPUT_TOKENS = 220        # 出力コスト抑制
CARDS_JSON_PATH = Path("data/cards.json")
IMAGES_DIR = Path("images")

# 簡易入場コード（未設定なら無効）
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

# =========================
# セッション状態初期化
# =========================
today = str(date.today())

if "count" not in st.session_state:
    st.session_state.count = 0

if "last_date" not in st.session_state:
    st.session_state.last_date = today

if "last_click_time" not in st.session_state:
    st.session_state.last_click_time = 0.0

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 日付が変わったらリセット
if st.session_state.last_date != today:
    st.session_state.count = 0
    st.session_state.last_date = today

# =========================
# secrets / API client
# =========================
api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("OPENAI_API_KEY が設定されていません。")
    st.stop()

client = OpenAI(api_key=api_key)

# =========================
# 簡易パスコード認証
# ※ 一般公開での無差別利用を少し減らす用
# =========================
if APP_PASSWORD:
    st.caption("利用には入場コードが必要です")
    with st.form("login_form"):
        password_input = st.text_input("入場コード", type="password")
        login_clicked = st.form_submit_button("入る")

    if login_clicked:
        if password_input == APP_PASSWORD:
            st.session_state.authenticated = True
        else:
            st.error("入場コードが違います。")

    if not st.session_state.authenticated:
        st.stop()

# =========================
# キャッシュ対象
# cards.json は毎回読まずキャッシュ
# =========================
@st.cache_data
def load_cards():
    with open(CARDS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# 同じ「テーマ×カード×向き×意味」は全ユーザー共通でキャッシュ
# これにより、同じ組み合わせへの再アクセスでAPI料金を抑えやすい
@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def get_tarot_reading(theme: str, card_name: str, orientation: str, meaning: str) -> str:
    prompt = f"""
あなたは優しく分かりやすいタロット占い師です。
以下のカード結果を初心者向けに解説してください。

【テーマ】
{theme}

【カード】
{card_name}（{orientation}）

【キーワード】
{meaning}

条件:
・必ず200以内にまとめること
・具体的な日常に落とし込む
・最後に一言アドバイス
・曖昧なスピリチュアル表現だけで済ませず、行動に落とし込む
"""

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    text = getattr(response, "output_text", None)
    if not text:
        raise RuntimeError("占い結果を取得できませんでした。")
    return text.strip()

# =========================
# UI
# =========================
st.markdown("## 🔮 AIタロット占い")
st.write("テーマを選んで、1枚引きで占います")

remaining_placeholder = st.empty()

# 初期表示
remaining = max(0, DAILY_LIMIT - st.session_state.count)
remaining_placeholder.caption(f"本日あと {remaining} 回")

if st.session_state.count >= DAILY_LIMIT:
    st.warning("本日の占い回数は終了しました。")
    st.stop()

theme = st.selectbox("占うテーマを選択", ["金運", "仕事運", "恋愛運", "総合運"])

# cards.json 読み込み
try:
    cards = load_cards()
except Exception:
    st.error("カードデータの読み込みに失敗しました。配置を確認してください。")
    st.stop()

col1, col2 = st.columns([3, 1])
with col2:
    button_clicked = st.button("占う", key="fortune_button", use_container_width=True)

# =========================
# 実行
# =========================
if button_clicked:
    now = time.time()

    # クールダウン
    elapsed = now - st.session_state.last_click_time
    if elapsed < COOLDOWN_SECONDS:
        wait_sec = int(COOLDOWN_SECONDS - elapsed) + 1
        st.warning(f"連続実行を防ぐため、あと {wait_sec} 秒待ってください。")
        st.stop()

    st.session_state.last_click_time = now

    with st.spinner("🔮 占い中... 少し待ってください"):
        try:
            card = random.choice(cards)
            orientation = random.choice(["正位置", "逆位置"])
            meaning = card["meaning_upright"] if orientation == "正位置" else card["meaning_reversed"]

            # APIコール（キャッシュあり）
            result = get_tarot_reading(
                theme=theme,
                card_name=card["name"],
                orientation=orientation,
                meaning=meaning,
            )

            st.subheader("🃏 結果")

            image_path = IMAGES_DIR / f"{card['number']}.jpg"
            if image_path.exists():
                img = Image.open(image_path)
                if orientation == "逆位置":
                    img = img.rotate(180)
                st.image(img, caption=f"{card['name']}（{orientation}）", width=250)
            else:
                st.info("カード画像が見つからないため、テキストのみ表示します。")

            st.write(f"カード：{card['name']}（{orientation}）")
            st.write(f"キーワード：{meaning}")

            st.subheader("🔮 解釈")
            st.write(result)

            # 成功時のみ回数消費
            st.session_state.count += 1

            remaining = max(0, DAILY_LIMIT - st.session_state.count)
            st.caption(f"残り回数: {remaining}")

        except Exception:
            # 公開時は詳細な例外をそのまま出しすぎない
            st.error("現在占いを実行できません。時間をおいて再度お試しください。")