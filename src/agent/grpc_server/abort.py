import grpc

def _abort_unary_unary(code: grpc.StatusCode, details: str):
    """unary-unary: 普通请求 -> 普通响应"""
    def terminate(ignored_request, context):
        context.abort(code, details)
    return grpc.unary_unary_rpc_method_handler(terminate)


def _abort_unary_stream(code: grpc.StatusCode, details: str):
    """unary-stream: 普通请求 -> 流式响应（服务端流式）"""
    def terminate(ignored_request, context):
        context.abort(code, details)
    return grpc.unary_stream_rpc_method_handler(terminate)


def _abort_stream_unary(code: grpc.StatusCode, details: str):
    """stream-unary: 流式请求 -> 普通响应（客户端流式）"""
    def terminate(ignored_request, context):
        context.abort(code, details)
    return grpc.stream_unary_rpc_method_handler(terminate)


def _abort_stream_stream(code: grpc.StatusCode, details: str):
    """stream-stream: 流式请求 -> 流式响应（双向流式）"""
    def terminate(ignored_request, context):
        context.abort(code, details)
    return grpc.stream_stream_rpc_method_handler(terminate)

def _abort_like_handler(handler, code: grpc.StatusCode, details: str):
    """
    请求端获取对应的函数
    根据 continuation 返回的 handler 的 request_streaming/response_streaming
    自动返回同类型的 abort handler。
    """
    req_stream = bool(getattr(handler, "request_streaming", False))
    resp_stream = bool(getattr(handler, "response_streaming", False))

    if req_stream and resp_stream:
        return _abort_stream_stream(code, details)
    if req_stream and not resp_stream:
        return _abort_stream_unary(code, details)
    if not req_stream and resp_stream:
        return _abort_unary_stream(code, details)
    return _abort_unary_unary(code, details)
