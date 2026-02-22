"""
RQ Worker 配置
处理视频切分任务
"""
import os
import platform
from redis import Redis
from rq import Worker, Queue, Connection, SimpleWorker
import logging

from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Redis 连接
redis_conn = Redis.from_url(settings.REDIS_URL)


def run_worker():
    """启动 RQ Worker"""
    # macOS + PyTorch/OpenCV 场景下，fork 子进程可能触发 ObjC 初始化崩溃。
    # 这里优先使用非 fork 的 SimpleWorker，保证任务稳定执行。
    worker_cls = Worker
    if platform.system() == "Darwin":
        os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
        worker_cls = SimpleWorker

    logging.info("RQ worker class selected: %s", worker_cls.__name__)
    with Connection(redis_conn):
        worker = worker_cls([Queue('default')])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    logging.info("启动 RQ Worker...")
    run_worker()
