"""Streamlit 前端：登录 + Agent 对话 + 检索 + 文件上传"""

import os
import json
import time
import uuid
import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")

# ---------- 会话状态初始化 ----------
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None


def auth_headers():
    """构造带 token 的请求头"""
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


# ---------- 侧边栏：登录 / 注册 ----------
st.sidebar.title("🔐 登录")
auth_mode = st.sidebar.radio("模式", ["登录", "注册"])

if st.session_state.access_token:
    st.sidebar.success("已登录")
    if st.sidebar.button("退出登录"):
        try:
            requests.post(f"{API_BASE}/auth/logout", headers=auth_headers())
        except Exception:
            pass
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.messages = []
        st.session_state.session_id = None
        st.rerun()
else:
    username = st.sidebar.text_input("用户名")
    password = st.sidebar.text_input("密码", type="password")
    if st.sidebar.button("提交"):
        url = f"{API_BASE}/auth/login" if auth_mode == "登录" else f"{API_BASE}/auth/register"
        resp = requests.post(url, json={"username": username, "password": password})
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.access_token = data["access_token"]
            st.session_state.refresh_token = data["refresh_token"]
            # 每个用户/每次登录生成独立会话，避免跨用户共享历史
            st.session_state.session_id = uuid.uuid4().hex[:16]
            st.session_state.messages = []
            st.sidebar.success("登录成功!")
            st.rerun()
        else:
            st.sidebar.error(resp.json().get("detail", "失败"))

# ---------- 主界面 ----------
st.title("🤖 Code Assistant Agent")
st.caption("基于 TinyDB 代码库的 AI 助手")

# 未登录就显示提示
if not st.session_state.access_token:
    st.info("请先在左侧登录或注册")
    st.stop()

# ---------- Tab: 对话 / 检索 / 上传 ----------
tab_chat, tab_search, tab_upload = st.tabs(["💬 对话", "🔍 检索", "📁 上传"])

# --- 对话 Tab ---
with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("问点 TinyDB 的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 思考中..."):
                resp = requests.post(
                    f"{API_BASE}/agent/chat",
                    json={"message": prompt, "session_id": st.session_state.session_id or "default"},
                    headers=auth_headers(),
                    timeout=120,
                )
            if resp.status_code == 200:
                answer = resp.json()["answer"]
            else:
                answer = f"错误: {resp.text}"
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

# --- 检索 Tab ---
with tab_search:
    query = st.text_input("输入检索查询（英文效果更好）")
    top_k = st.slider("返回条数", 1, 10, 5)
    if st.button("检索") and query:
        resp = requests.post(
            f"{API_BASE}/search",
            json={"query": query, "top_k": top_k},
            headers=auth_headers(),
            timeout=60,
        )
        if resp.status_code == 200:
            results = resp.json()["results"]
            if not results:
                st.info("没有找到结果")
            for r in results:
                st.markdown(f"**{r['source']}**")
                st.code(r["text"][:300], language="python")
        else:
            st.error(resp.json().get("detail", "检索失败"))

# --- 上传 Tab ---
with tab_upload:
    uploaded = st.file_uploader("上传代码文件", type=["py", "js", "md", "txt"])
    if uploaded and st.button("上传并索引"):
        resp = requests.post(
            f"{API_BASE}/upload",
            files={"file": (uploaded.name, uploaded.getvalue(), "text/plain")},
            headers=auth_headers(),
            timeout=60,
        )
        if resp.status_code == 200:
            st.success(f"索引成功: {resp.json()['chunk_count']} chunks")
        else:
            st.error(resp.json().get("detail", "上传失败"))