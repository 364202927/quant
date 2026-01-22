# from typing import TYPE_CHECKING, List, Any
from server.core.quant import quant


class msgHandler:
    """消息处理器 - 接收并处理来自webport和cli的消息"""
    
    def __init__(self, objQuant: 'quant'):
        self.__instance = objQuant
    

    # 处理接口
    def process(self, id, msg):
        # id = msg.get('id', None)
        # args = msg.get('args', [])
        print(f"~~~~~~~~~~[消息处理]~~~~~~~~ 消息ID: {id}, 参数: {msg}")
        return 0
