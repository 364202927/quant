import uuid,json
from collections import deque
from server.utils.common import str2time
# from datetime import datetime
from typing import Any


class recordBuffer:
    "日志buffer"

    def __init__(self, filePath: str = '', max_size: int = 1024):
        self._buffer: deque[dict] = deque(maxlen=max_size)
        self._filePath = filePath
        self._printIdx = 0  # 记录已打印位置
        self._index_map: dict[str, dict] = {}
        # if filePath: #todo先移除
        #     self.readFile(filePath, isFull=True)

    # tags:索引标签, time:保存的时间
    def push(self, **kwargs: Any):
        log_id = uuid.uuid4().hex[:8]
        time = kwargs.pop('time', str2time('strNow'))
        tags = kwargs.pop('tags', [str(t) for t in kwargs])
        buffer = {'id': log_id,
                    'time': time,
                    'tags': tags,
                    'data': kwargs}
        self._buffer.append(buffer)
        self._index_map[log_id] = buffer
        return log_id
    #tags
    def get(self, se_time:tuple[str, str]|None = None,match = True,**kwargs: Any) -> list[dict]:
        result = []
        search_items = kwargs.items() if kwargs else None
        start_time = se_time[0] if se_time and len(se_time) > 0 else None
        end_time = se_time[1] if se_time and len(se_time) > 1 else None
        for r in self._buffer:
            # 时间范围校验
            if start_time and r['time'] < start_time:
                continue
            if end_time and r['time'] > end_time:
                continue
            # tags值匹配
            if search_items:
                data_dict = r.get('tags', {})
                if match:                   
                    if not all(data_dict.get(k) == v for k, v in search_items):
                        continue
                else:
                    if not any(data_dict.get(k) == v for k, v in search_items):
                        continue
            result.append(r)
        return result

    def getNew(self) -> list[dict]:
        items = list(self._buffer)
        new_items = items[self._printIdx:]
        self._printIdx = len(items)
        return new_items
    #日志更新
    def update(self, id: str, **kwargs: Any) -> bool:
        record = self._index_map.get(id)
        if not record:
            return False
        if kwargs.get('tags'):
            record['tags'] = kwargs['tags']
            del kwargs['tags']        
        if kwargs:
            record['data'].update(kwargs)
        return True
    #文件操作
    def save2File(self, file_split: str = 'Y') -> bool:
        """记录到文件（JSON Lines 格式）"""
        # if not self._buffer or not self._filePath:
        #     return False
        # from server.utils.common import genFileName
        # filename = genFileName(self._filePath, file_split, 'log')
        # with open(filename, 'a', encoding='utf-8') as f:
        #     for record in self._buffer:
        #         f.write(json.dumps(record, ensure_ascii=False) + '\n')
        # return True
    def readFile(self, filePath: str, isFull: bool = False) -> bool:
        """读取缓存文件填充buffer, isFull=True全量读取, False只读最近一个文件"""
        # from server.utils.common import path2File, joinPath
        # files = path2File(filePath, '.log')
        # if not files:
        #     return False
        # if not isFull:
        #     files = files[-1:]
        # for f in files:
        #     fullPath = joinPath(filePath, f)
        #     try:
        #         with open(fullPath, 'r', encoding='utf-8') as fh:
        #             for line in fh:
        #                 line = line.strip()
        #                 if line:
        #                     self._buffer.append(json.loads(line))
        #     except (json.JSONDecodeError, IOError):
        #         continue
        # return True
    def archive(self)->None:
        pass

    def clear(self) -> None:
        self._buffer.clear()
        self._index_map.clear()
        self._printIdx = 0
    def size(self) -> int:
        return len(self._buffer)
    def buffer(self) -> list[dict]:
        return self._buffer#list(self._buffer)