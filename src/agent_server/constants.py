from uuid import UUID

# 그래프 ID로부터 결정론적 어시스턴트 ID를 파생하기 위한 표준 네임스페이스 UUID.
# 중요: 데이터 마이그레이션을 계획하지 않는 한 초기 배포 후 변경하지 마십시오.
ASSISTANT_NAMESPACE_UUID = UUID("6ba7b821-9dad-11d1-80b4-00c04fd430c8")
