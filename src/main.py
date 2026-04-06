import streamlit as st
import os
import json
import random
from PIL import Image
from openai import OpenAI

st.set_page_config(
    page_title="AIタロット占い",
    page_icon="🔮"
)

# 環境変数読み込み
st.set_page_config(page_title="AIタロット占い", page_icon="🔮")

api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=api_key)

# タイトル
st.title("🔮 AIタロット占い")
st.write("テーマを選んで、1枚引きで占います")

# テーマ選択
theme = st.selectbox("占うテーマを選択", ["金運", "仕事運", "恋愛運", "総合運"])

# JSON読み込み
with open("data/cards.json", "r", encoding="utf-8") as f:
    cards = json.load(f)

# ボタン
if st.button("占う"):
    with st.spinner("🔮 占い中... 少し待ってください"):
        card = random.choice(cards)
        orientation = random.choice(["正位置", "逆位置"])

        if orientation == "正位置":
            meaning = card["meaning_upright"]
        else:
            meaning = card["meaning_reversed"]

        prompt = f"""
あなたは優しく分かりやすいタロット占い師です。
以下のカード結果を初心者向けに解説してください。

【テーマ】
{theme}

【カード】
{card["name"]}（{orientation}）

【キーワード】
{meaning}

条件:
・200〜300文字
・具体的な日常に落とし込む
・最後に一言アドバイス
"""

        try:
            response = client.responses.create(model="gpt-4.1-mini", input=prompt)

            result = response.output_text

            st.subheader("🃏 結果")

            image_path = os.path.join("images", f"{card['number']}.jpg")
            img = Image.open(image_path)


            if orientation == "逆位置":
                img = img.rotate(180)

            st.image(img, caption=f"{card['name']}（{orientation}）", width=250)
            

            st.write(f"カード：{card['name']}（{orientation}）")
            st.write(f"キーワード：{meaning}")

            st.subheader("🔮 解釈")
            st.write(result)

        except Exception as e:
            st.error(f"エラー: {e}")
