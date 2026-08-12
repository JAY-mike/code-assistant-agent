"""Streamlit 前端：登录、Agent 对话、检索和文件上传。"""

import json
import os
import uuid
from urllib.parse import quote

import requests
import streamlit as st


API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000/api")
KNOWLEDGE_BASE_LABELS = {
    "tinydb": "TinyDB 开源项目",
    "project": "当前 Code Assistant Agent 项目",
}


if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.access_token}"}


def response_detail(response, fallback: str) -> str:
    try:
        detail = response.json().get("detail", fallback)
    except (ValueError, AttributeError):
        return fallback
    return detail if isinstance(detail, str) else fallback


def safe_post(*args, **kwargs):
    try:
        return requests.post(*args, **kwargs)
    except requests.RequestException:
        return None


def get_chat_session(knowledge_base: str) -> dict:
    if knowledge_base not in st.session_state.chat_sessions:
        st.session_state.chat_sessions[knowledge_base] = {
            "session_id": uuid.uuid4().hex[:16],
            "messages": [],
        }
    return st.session_state.chat_sessions[knowledge_base]


def render_execution_trace(trace: list[dict]):
    """Render tool execution summaries without exposing model reasoning."""
    if not trace:
        return

    status_labels = {
        "completed": "完成",
        "rejected": "参数被拒绝",
        "failed": "执行失败",
    }
    with st.expander("执行轨迹", expanded=False):
        for item in trace:
            status = status_labels.get(item["status"], item["status"])
            st.caption(f"步骤 {item['step']} · {item['tool_name']} · {status}")
            if item.get("arguments"):
                st.code(json.dumps(item["arguments"], ensure_ascii=False), language="json")
            if item.get("observation"):
                st.code(item["observation"], language="text")


st.sidebar.title("🔐 登录")
auth_mode = st.sidebar.radio("模式", ["登录", "注册"])

def render_citations(citations: list[dict], scope: str):
    if not citations:
        return

    with st.expander("引用代码", expanded=False):
        for index, citation in enumerate(citations):
            st.caption(citation["source"])
            st.code(citation["excerpt"], language="python")
            source_url = (
                f"{API_BASE}/search/source?knowledge_base="
                f"{quote(citation['knowledge_base'])}&source={quote(citation['source'])}"
            )
            if st.button("查看完整源码", key=f"source_{scope}_{index}"):
                try:
                    response = requests.get(source_url, headers=auth_headers(), timeout=15)
                    if response.status_code == 200:
                        st.code(response.json()["content"], language="python")
                    else:
                        st.error(response_detail(response, "读取源码失败"))
                except requests.RequestException as exc:
                    st.error(f"读取源码失败: {exc}")


def render_performance_metrics(metrics: dict):
    if not metrics:
        return

    st.caption(
        "服务端耗时 "
        f"{metrics['server_e2e_latency_ms']:.0f} ms | "
        f"Agent {metrics['agent_latency_ms']:.0f} ms | "
        f"工具 {metrics['tool_latency_ms']:.0f} ms"
    )
    if metrics.get("time_to_first_token_ms") is not None:
        st.caption(f"流式首 token {metrics['time_to_first_token_ms']:.0f} ms")


def iter_sse_events(response):
    event_name = "message"
    data = None
    for raw_line in response.iter_lines(decode_unicode=True):
        line = raw_line.strip() if raw_line else ""
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            try:
                data = json.loads(line.removeprefix("data:").strip())
            except json.JSONDecodeError:
                continue
        elif not line and data is not None:
            yield event_name, data
            event_name = "message"
            data = None


if st.session_state.access_token:
    st.sidebar.success("已登录")
    if st.sidebar.button("退出登录"):
        try:
            requests.post(f"{API_BASE}/auth/logout", headers=auth_headers())
        except Exception:
            pass
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.session_state.chat_sessions = {}
        st.rerun()
else:
    username = st.sidebar.text_input("用户名")
    password = st.sidebar.text_input("密码", type="password")
    if st.sidebar.button("提交"):
        url = f"{API_BASE}/auth/login" if auth_mode == "登录" else f"{API_BASE}/auth/register"
        try:
            response = requests.post(
                url, json={"username": username, "password": password}, timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                st.session_state.access_token = data["access_token"]
                st.session_state.refresh_token = data["refresh_token"]
                st.session_state.chat_sessions = {}
                st.sidebar.success("登录成功")
                st.rerun()
            else:
                st.sidebar.error(response_detail(response, "登录失败"))
        except (requests.RequestException, KeyError, ValueError):
            st.sidebar.error("无法连接后端，请确认服务已启动后重试。")


st.title("🤖 Code Assistant Agent")
st.caption("基于 TinyDB 与项目源码的代码检索助手")

if not st.session_state.access_token:
    st.info("请先在左侧登录或注册")
    st.stop()


tab_chat, tab_search, tab_upload = st.tabs(["💬 对话", "🔍 检索", "📁 上传"])

with tab_chat:
    chat_knowledge_base = st.selectbox(
        "对话知识库",
        options=list(KNOWLEDGE_BASE_LABELS),
        format_func=KNOWLEDGE_BASE_LABELS.__getitem__,
        key="chat_knowledge_base",
    )
    chat_session = get_chat_session(chat_knowledge_base)
    for message_index, message in enumerate(chat_session["messages"]):
        with st.chat_message(message["role"]):
            if message.get("failed"):
                st.error(message["content"])
            else:
                st.markdown(message["content"])
            if message["role"] == "assistant":
                render_execution_trace(message.get("trace", []))
                render_citations(message.get("citations", []), f"history_{message_index}")
                render_performance_metrics(message.get("metrics", {}))

    if prompt := st.chat_input("问代码库中的实现细节..."):
        chat_session["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent 处理中..."):
                streamed = False
                failed = False
                citations = []
                metrics = {}
                trace = []
                answer = ""
                response = None
                try:
                    response = requests.post(
                        f"{API_BASE}/agent/chat/stream",
                        json={
                            "message": prompt,
                            "session_id": chat_session["session_id"],
                            "knowledge_base": chat_knowledge_base,
                        },
                        headers=auth_headers(),
                        timeout=90,
                        stream=True,
                    )
                    if response.status_code == 200:
                        streamed = True
                        answer_parts = []
                        answer_placeholder = st.empty()
                        status_placeholder = st.empty()
                        for event, data in iter_sse_events(response):
                            if event == "status":
                                status_placeholder.caption(data["message"])
                            elif event == "trace":
                                trace.append(data["trace"])
                            elif event == "delta":
                                answer_parts.append(data["text"])
                                answer_placeholder.markdown("".join(answer_parts))
                            elif event == "done":
                                citations = data.get("citations", [])
                                metrics = data.get("metrics", {})
                            elif event == "error":
                                answer = data.get("message", "Agent 执行失败")
                                failed = True
                                answer_placeholder.error(answer)
                                break
                            elif event == "cancelled":
                                answer = data.get("message", "生成已取消")
                                failed = True
                                status_placeholder.warning(answer)
                                break
                        status_placeholder.empty()
                        if not failed:
                            answer = "".join(answer_parts).strip()
                        if not failed and not answer:
                            answer = "Agent 未返回内容，请稍后重试。"
                            failed = True
                    else:
                        answer = response_detail(response, "Agent 请求失败")
                        failed = True
                except requests.Timeout:
                    answer = "请求等待时间过长，Agent 未能及时完成。请缩小问题范围后重试。"
                    failed = True
                except requests.RequestException as exc:
                    answer = f"请求失败: {exc}"
                    failed = True
                finally:
                    if response is not None:
                        response.close()
            if failed:
                st.error(answer)
            elif not streamed:
                st.markdown(answer)
            if not failed:
                render_execution_trace(trace)
                render_citations(citations, f"response_{len(chat_session['messages'])}")
                render_performance_metrics(metrics)
            if not failed:
                chat_session["messages"].append({
                    "role": "assistant",
                    "content": answer,
                    "trace": trace,
                    "citations": citations,
                    "metrics": metrics,
                })

with tab_search:
    search_knowledge_base = st.selectbox(
        "检索知识库",
        options=list(KNOWLEDGE_BASE_LABELS),
        format_func=KNOWLEDGE_BASE_LABELS.__getitem__,
        key="search_knowledge_base",
    )
    query = st.text_input("输入检索查询")
    top_k = st.slider("返回条数", 1, 10, 5)
    if st.button("检索") and query:
        response = safe_post(
            f"{API_BASE}/search",
            json={
                "query": query,
                "knowledge_base": search_knowledge_base,
                "top_k": top_k,
            },
            headers=auth_headers(),
            timeout=60,
        )
        if response is None:
            st.error("检索请求失败，请稍后重试。")
        elif response.status_code == 200:
            results = response.json()["results"]
            if not results:
                st.info("没有找到结果")
            for result in results:
                st.markdown(f"**{result['source']}**")
                st.code(result["text"][:300], language="python")
        else:
            st.error(response_detail(response, "检索失败"))

with tab_upload:
    uploaded = st.file_uploader("上传代码文件", type=["py", "js", "md", "txt"])
    if uploaded and st.button("上传并索引"):
        response = safe_post(
            f"{API_BASE}/upload",
            files={"file": (uploaded.name, uploaded.getvalue(), "text/plain")},
            headers=auth_headers(),
            timeout=60,
        )
        if response is None:
            st.error("上传请求失败，请稍后重试。")
        elif response.status_code == 200:
            st.success(f"索引成功: {response.json()['chunk_count']} chunks")
        else:
            st.error(response_detail(response, "上传失败"))

    upload_query = st.text_input("查询自己上传的内容")
    if st.button("检索上传内容") and upload_query:
        response = safe_post(
            f"{API_BASE}/upload/search",
            json={"query": upload_query, "top_k": 5},
            headers=auth_headers(),
            timeout=60,
        )
        if response is None:
            st.error("检索请求失败，请稍后重试。")
        elif response.status_code == 200:
            results = response.json()["results"]
            if not results:
                st.info("没有找到结果")
            for result in results:
                st.markdown(f"**{result['source']}**")
                st.code(result["text"][:300], language="python")
        else:
            st.error(response_detail(response, "检索失败"))
