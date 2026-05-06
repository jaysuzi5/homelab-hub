import time
import uuid
import logging
from django.conf import settings
from django.shortcuts import redirect
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from hub.otel import _SKIP_PREFIXES

_mw_logger = logging.getLogger(__name__)


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        exempt_urls = [
            settings.LOGIN_URL,
            "/accounts/signup/",
            "/accounts/logout/",
            "/admin/",
            "/accounts/google/login/",
            "/accounts/google/login/callback/",
        ]

        if not request.user.is_authenticated and not any(request.path.startswith(url) for url in exempt_urls):
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)


class PageLoggingMiddleware:
    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        from hub.otel import setup_otel
        setup_otel()
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def __call__(self, request):
        if iscoroutinefunction(self):
            return self.__acall__(request)
        return self._sync_call(request)

    def _skip(self, path):
        return any(path.startswith(p) for p in _SKIP_PREFIXES)

    def _start_request(self, request):
        transaction_id = str(uuid.uuid4())
        request.otel_transaction_id = transaction_id

        if self._skip(request.path):
            return None, transaction_id, time.monotonic(), None

        try:
            from hub.otel import _endpoint_from_path, log_request, _tracer
            endpoint = _endpoint_from_path(request.path)
            log_request(request, transaction_id, endpoint)

            span = None
            if _tracer is not None:
                from opentelemetry import trace as otel_trace
                span = _tracer.start_span(
                    endpoint,
                    kind=otel_trace.SpanKind.SERVER,
                    attributes={
                        "http.method": request.method,
                        "http.path": request.path,
                        "transaction_id": transaction_id,
                    },
                )
            return endpoint, transaction_id, time.monotonic(), span
        except Exception:
            _mw_logger.exception("PageLoggingMiddleware._start_request failed")
            return request.path, transaction_id, time.monotonic(), None

    def _finish_request(self, request, response, endpoint, transaction_id, start, span):
        if endpoint is None:
            return
        try:
            from hub.otel import log_response, _page_visits
            duration = time.monotonic() - start
            summary = getattr(request, "otel_page_summary", {"page": endpoint})

            trace_id = span_id = None
            if span is not None:
                try:
                    span.set_attribute("http.status_code", response.status_code)
                    ctx = span.get_span_context()
                    if ctx and ctx.is_valid:
                        trace_id = format(ctx.trace_id, "032x")
                        span_id = format(ctx.span_id, "016x")
                    span.end()
                except Exception:
                    pass

            log_response(request, transaction_id, endpoint, response.status_code, duration, summary, trace_id, span_id)

            if _page_visits is not None:
                _page_visits.add(1, {
                    "endpoint": endpoint,
                    "method": request.method,
                    "status": str(response.status_code),
                })
        except Exception:
            _mw_logger.exception("PageLoggingMiddleware._finish_request failed")

    def _sync_call(self, request):
        endpoint, transaction_id, start, span = self._start_request(request)
        response = self.get_response(request)
        self._finish_request(request, response, endpoint, transaction_id, start, span)
        return response

    async def __acall__(self, request):
        endpoint, transaction_id, start, span = self._start_request(request)
        response = await self.get_response(request)
        self._finish_request(request, response, endpoint, transaction_id, start, span)
        return response
