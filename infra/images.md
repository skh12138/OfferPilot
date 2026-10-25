# 容器版本

2026-10-23 用 docker buildx imagetools inspect 核对的镜像索引 digest；Dockerfile/Compose 同时锁定标签与 digest。

| 用途 | 标签 | SHA256 |
| --- | --- | --- |
| 数据库 | postgres:17.6-bookworm | f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3 |
| Python | python:3.12.14-slim-bookworm | 392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e |
| Web 构建 | node:24.19.0-bookworm-slim | a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df |
| Web 运行 | caddy:2.10.2-alpine | 4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d |

Python 构建安装 uv==0.13.5；Node 构建安装 pnpm@11.25.0，依赖分别按 uv.lock 与 pnpm-lock.yaml 冻结。Python 非 root 用户运行。更新版本需重新构建、验证与记录 digest，不使用 latest。
