---
name: learned-http_client-11
description: >
  Python HTTP 调用封装模式：创建 httpx.Client 前 pop HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy/all_proxy/ALL
source: learnings #11
date: 2026-06-06 10:50:39
---

# Http_Client Pattern

Python HTTP 调用封装模式：创建 httpx.Client 前 pop HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy/all_proxy/ALL_PROXY 六个环境变量。已封装在 genark/engine/genark/http_client.py 的 _http_client() 中，所有 HTTP 调用用它。
