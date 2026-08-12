import uuid, os
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
        evicted = self._buffer[0] if len(self._buffer) == self._buffer.maxlen else None
        self._buffer.append(buffer)
        if evicted is not None:
            self._index_map.pop(evicted['id'], None)
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
        os.makedirs(self._filePath, exist_ok=True)
        for day, records in groups.items():
            filename = joinPath(self._filePath, f'{day}.jsonl')
            writeFile(records, filename, 'a')
            # data = json.dumps(record, ensure_ascii=False, default=str) + '\n'
            # with open(filename, 'a', encoding='utf-8') as f:
            #     for record in records:
            #         f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
        self._saveIdx = len(items)
        return True
    #加载数据: days=N 只加载最近N天, days=None 全量扫描目录下所有历史文件
    def readFile(self, days: int | None = 7) -> bool:
        if not self._filePath:
            return False
        loaded = 0
        if days is None:
            if not os.path.isdir(self._filePath):
                return False
            filenames = sorted(
                joinPath(self._filePath, f) for f in os.listdir(self._filePath) if f.endswith('.jsonl')
            )
        else:
            today = datetime.now()
            filenames = [
                joinPath(self._filePath, f'{(today - timedelta(days=i)).strftime("%Y-%m-%d")}.jsonl')
                for i in range(days, -1, -1)
            ]
        seen = {record.get('id') for record in self._buffer}
        for filename in filenames:
            records = readFile(filename)
            if not records:
                continue
            for record in records:
                recordId = record.get('id')
                if recordId in seen:
                    continue
                self._buffer.append(record)
                seen.add(recordId)
                loaded += 1
        self._index_map = {r['id']: r for r in self._buffer}
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
