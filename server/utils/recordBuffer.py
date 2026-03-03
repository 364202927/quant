from collections import deque
from server.utils.common import str2time
# from datetime import datetime
from typing import Any
import json

class recordBuffer:
    "日志buffer"

    def __init__(self, filePath: str = '', max_size: int = 1024):
        self._buffer: deque[dict] = deque(maxlen=max_size)
        self._filePath = filePath
        self._printIdx = 0  # 记录已打印位置
        # if filePath: #todo先移除
        #     self.readFile(filePath, isFull=True)
    #
    def push(self, **kwargs: Any) -> None:
        time = kwargs.get('time') and kwargs.get('time')or str2time('strNow')
        tags = kwargs.get('tags') and kwargs.get('tags') or [str(t) for t in kwargs]
        if kwargs.get('time'):del kwargs['time']
        if kwargs.get('tags'):del kwargs['tags']
        buffer = {'time':time,
                'tags':tags,
                'data':kwargs}
        self._buffer.append(buffer)
    def get(self, *tags: str | int, match_all: bool = False,
            start_time: str | None = None, end_time: str | None = None) -> list[dict]:
        """按标签和时间范围过滤数据"""
        result = list(self._buffer)

        if tags:
            search_tags = {str(t) for t in tags}
            check = (lambda r: search_tags <= set(r['tags'])) if match_all \
                else (lambda r: search_tags & set(r['tags']))
            result = [r for r in result if check(r)]

        if start_time:
            result = [r for r in result if r['time'] >= start_time]
        if end_time:
            result = [r for r in result if r['time'] <= end_time]
        return result
    def getNew(self) -> list[dict]:
        """获取上次调用后新增的记录"""
        items = list(self._buffer)
        new_items = items[self._printIdx:]
        self._printIdx = len(items)
        return new_items

    def save2File(self, file_split: str = 'Y') -> bool:
        """记录到文件（JSON Lines 格式）"""
        if not self._buffer or not self._filePath:
            return False
        from server.utils.common import genFileName
        filename = genFileName(self._filePath, file_split, 'log')
        with open(filename, 'a', encoding='utf-8') as f:
            for record in self._buffer:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        return True
    def readFile(self, filePath: str, isFull: bool = False) -> bool:
        """读取缓存文件填充buffer, isFull=True全量读取, False只读最近一个文件"""
        from server.utils.common import path2File, joinPath
        files = path2File(filePath, '.log')
        if not files:
            return False
        if not isFull:
            files = files[-1:]
        for f in files:
            fullPath = joinPath(filePath, f)
            try:
                with open(fullPath, 'r', encoding='utf-8') as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            self._buffer.append(json.loads(line))
            except (json.JSONDecodeError, IOError):
                continue
        return True
    def archive(self)->None:
        pass

    def clear(self) -> None:
        self._buffer.clear()
        self._printIdx = 0
    def size(self) -> int:
        return len(self._buffer)
    def all(self) -> list[dict]:
        return list(self._buffer)