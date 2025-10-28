"""StreamingService unit tests

테스트 커버리지 개선을 위한 핵심 함수 테스트
"""


from src.agent_server.services.streaming_service import StreamingService


class TestStreamingServiceInit:
    """StreamingService 초기화 테스트"""

    def test_initialization(self):
        """서비스가 올바르게 초기화되는지 검증"""
        service = StreamingService()

        assert service.event_counters == {}
        assert service.event_converter is not None


class TestProcessInterruptUpdates:
    """_process_interrupt_updates 메서드 테스트"""

    def setup_method(self):
        """각 테스트 전 StreamingService 인스턴스 생성"""
        self.service = StreamingService()

    def test_process_interrupt_updates_skip_non_interrupt(self):
        """인터럽트가 아닌 updates 이벤트는 스킵"""
        raw_event = ("updates", {"key": "value"})
        only_interrupt_updates = True

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        # 인터럽트가 아니므로 스킵
        assert should_skip is True

    def test_process_interrupt_updates_pass_interrupt(self):
        """인터럽트 업데이트는 values로 변환하여 통과"""
        raw_event = ("updates", {"__interrupt__": [{"type": "human"}]})
        only_interrupt_updates = True

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        # 인터럽트이므로 통과하고 values로 변환
        assert should_skip is False
        assert processed_event[0] == "values"

    def test_process_interrupt_updates_with_disabled_filter(self):
        """only_interrupt_updates=False일 때는 필터링 안함"""
        raw_event = ("updates", {"key": "value"})
        only_interrupt_updates = False

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        # 필터링 비활성화이므로 스킵 안함
        assert should_skip is False
        assert processed_event == raw_event

    def test_process_interrupt_updates_non_tuple_event(self):
        """튜플이 아닌 이벤트는 그대로 통과"""
        raw_event = {"event": "data"}
        only_interrupt_updates = True

        processed_event, should_skip = self.service._process_interrupt_updates(
            raw_event, only_interrupt_updates
        )

        assert should_skip is False
        assert processed_event == raw_event


