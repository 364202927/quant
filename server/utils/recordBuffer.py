import uuid, json#, os
from collections import deque, defaultdict
from datetime import datetime, timedelta
from server.utils.common import str2time, joinPath,writeFile,readFile
from typing import Any


class recordBuffer:
    "日志buffer"

    def __init__(self, filePath: str = '', max_size: int = 1024):
        self._buffer: deque[dict] = deque(maxlen=max_size)
        self._filePath = filePath   #todo:写入文件的位置
        self._printIdx = 0  # 记录已打印位置
        self._saveIdx = 0   # 记录已保存位置
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
        if kwargs.get('id'): #根据id返回
            return self._index_map.get(kwargs.get('id'))
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
    def update(self, id: str, **kwargs: Any) -> dict:
        record = self._index_map.get(id)
        if not record:
            return {}
        if kwargs.get('tags'):
            record['tags'] = kwargs['tags']
            del kwargs['tags']        
        if kwargs:
            record['data'].update(kwargs)
        return record
    #按天数写入数据
    def save2File(self) -> bool:
        if not self._filePath:
            return False
        items = list(self._buffer)
        unsaved = items[self._saveIdx:]
        if not unsaved:
            return True
        # 按日期分组
        groups: dict[str, list] = defaultdict(list)
        for record in unsaved:
            t = record['time']
            day_key = t.strftime('%Y-%m-%d') if hasattr(t, 'strftime') else str(t)[:10]
            groups[day_key].append(record)
        # 逐组写入
        # os.makedirs(self._filePath, exist_ok=True)
        for day, records in groups.items():
            filename = joinPath(self._filePath, f'{day}.jsonl')
            writeFile(records, filename, 'a')
            # data = json.dumps(record, ensure_ascii=False, default=str) + '\n'
            # with open(filename, 'a', encoding='utf-8') as f:
            #     for record in records:
            #         f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
        self._saveIdx = len(items)
        return True
    #加载day的数据
    def readFile(self, days: int = 7) -> bool:
        if not self._filePath:
            return False
        today = datetime.now()
        loaded = 0
        for i in range(days, -1, -1):
            day = today - timedelta(days=i)
            filename = joinPath(self._filePath, f'{day.strftime("%Y-%m-%d")}.jsonl')
            file = readFile(filename)
            for line in file:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                self._buffer.append(record)
                self._index_map[record['id']] = record
                loaded += 1
            # if not os.path.exists(filename):
            #     continue
            # try:
            #     with open(filename, 'r', encoding='utf-8') as f:
            #         for line in f:
            #             line = line.strip()
            #             if not line:
            #                 continue
            #             record = json.loads(line)
            #             self._buffer.append(record)
            #             self._index_map[record['id']] = record
            #             loaded += 1
            # except (json.JSONDecodeError, IOError):
            #     continue
        self._saveIdx = len(self._buffer)
        return loaded > 0

    def clear(self) -> None:
        self._buffer.clear()
        self._index_map.clear()
        self._printIdx = 0
        self._saveIdx = 0
    def size(self) -> int:
        return len(self._buffer)
    def buffer(self) -> list[dict]:
        return self._buffer#list(self._buffer)