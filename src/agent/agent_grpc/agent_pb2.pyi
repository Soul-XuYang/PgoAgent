from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UserConfig(_message.Message):
    __slots__ = ()
    THREAD_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CHAT_MODE_FIELD_NUMBER: _ClassVar[int]
    RECURSION_LIMIT_FIELD_NUMBER: _ClassVar[int]
    thread_id: str
    user_id: str
    chat_mode: str
    recursion_limit: int
    def __init__(self, thread_id: _Optional[str] = ..., user_id: _Optional[str] = ..., chat_mode: _Optional[str] = ..., recursion_limit: _Optional[int] = ...) -> None: ...

class ChatRequest(_message.Message):
    __slots__ = ()
    USER_INPUT_FIELD_NUMBER: _ClassVar[int]
    USER_CONFIG_FIELD_NUMBER: _ClassVar[int]
    user_input: str
    user_config: UserConfig
    def __init__(self, user_input: _Optional[str] = ..., user_config: _Optional[_Union[UserConfig, _Mapping]] = ...) -> None: ...

class ChatResponse(_message.Message):
    __slots__ = ()
    REPLY_FIELD_NUMBER: _ClassVar[int]
    TOKEN_USAGE_FIELD_NUMBER: _ClassVar[int]
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    reply: str
    token_usage: int
    success: bool
    error_message: str
    def __init__(self, reply: _Optional[str] = ..., token_usage: _Optional[int] = ..., success: _Optional[bool] = ..., error_message: _Optional[str] = ...) -> None: ...

class StreamChunk(_message.Message):
    __slots__ = ()
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    FINAL_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    NODE_NAME_FIELD_NUMBER: _ClassVar[int]
    output: str
    final_response: bool
    token: int
    node_name: str
    def __init__(self, output: _Optional[str] = ..., final_response: _Optional[bool] = ..., token: _Optional[int] = ..., node_name: _Optional[str] = ...) -> None: ...

class HistoryRequest(_message.Message):
    __slots__ = ()
    USER_CONFIG_FIELD_NUMBER: _ClassVar[int]
    user_config: UserConfig
    def __init__(self, user_config: _Optional[_Union[UserConfig, _Mapping]] = ...) -> None: ...

class HistoryResponse(_message.Message):
    __slots__ = ()
    LATEST_CONVERSATION_FIELD_NUMBER: _ClassVar[int]
    CUMULATIVE_USAGE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    latest_conversation: _containers.RepeatedCompositeFieldContainer[ConversationPair]
    cumulative_usage: int
    summary: str
    def __init__(self, latest_conversation: _Optional[_Iterable[_Union[ConversationPair, _Mapping]]] = ..., cumulative_usage: _Optional[int] = ..., summary: _Optional[str] = ...) -> None: ...

class ConversationPair(_message.Message):
    __slots__ = ()
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    role: str
    content: str
    timestamp: int
    def __init__(self, role: _Optional[str] = ..., content: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class CancelRequest(_message.Message):
    __slots__ = ()
    THREAD_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    thread_id: str
    user_id: str
    def __init__(self, thread_id: _Optional[str] = ..., user_id: _Optional[str] = ...) -> None: ...

class CancelResponse(_message.Message):
    __slots__ = ()
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: _Optional[bool] = ..., message: _Optional[str] = ...) -> None: ...

class ServerInfo(_message.Message):
    __slots__ = ()
    VERSION_FIELD_NUMBER: _ClassVar[int]
    RUN_TIME_FIELD_NUMBER: _ClassVar[int]
    version: str
    run_time: str
    def __init__(self, version: _Optional[str] = ..., run_time: _Optional[str] = ...) -> None: ...
