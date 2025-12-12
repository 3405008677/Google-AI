## src/server 目录说明

## 概述
该目录负责组装并启动 FastAPI 服务，包括：
- 创建 FastAPI app（路由、中间件、异常处理器、静态文件）
- 生命周期管理（startup/shutdown）
- 日志初始化
- SSL 启动参数封装
- Uvicorn 启动封装（供 `src/main.py` 调用）

## 关键文件
- `app.py`：创建 FastAPI 应用（`create_app`）并挂载静态目录、异常处理等。
- `server.py`：封装 `uvicorn.run` 的启动流程（`initServer`）。
- `logging_setup.py`：日志器配置与获取。
- `lifespan.py`：应用生命周期事件。
- `exceptions.py`：全局异常处理器注册。
- `ssl_utils.py`：根据配置生成 SSL 相关启动参数。
- `middlewares.py`：服务级（全局）中间件实现。
