# Salesforce Opportunity Owner(영문 풀네임) -> sales-dashboard의 member 코드 / team 매핑.
# Firestore settings/layout.teams 에 등록된 실제 멤버 기준(2026-07-30 확인):
#   Team 1: Kim SH, Oh SG, Yoon DJ
#   Team 2: Baek SC, Lee GR, Kim BW
#   Team 3: Lim YC, GG Park
# Kim BW = "Kim Byungwook" (2026-08-27 확인).
# GG Park = "Park Gookgi", Jeong IY = "Jeong Ilyeong" (둘 다 Team 3, 2026-11-02 확인).
# 2026-08-27 기준 미매핑으로 남아 경고에 찍히는 owner: Park Yuna, Bang Yunseong.

OWNER_TO_MEMBER = {
    "Kim Sung Hoon": "Kim SH",
    "Oh Sang Geol": "Oh SG",
    "Baek Seung Chul": "Baek SC",
    "Lee Garam": "Lee GR",
    "Lim Yong Chul": "YC lim",   # 대시보드 표기와 통일(2026-11-02). "Lim YC"는 팀 설정에 없어 후보 등록 시 고아 멤버가 됐음
    "Yoon Dongjun": "Yoon DJ",
    "Kim Byungwook": "Kim BW",
    "Park Gookgi": "GG Park",    # 2026-11-02 사용자 확인
    "Jeong Ilyeong": "Jeong IY", # 2026-11-02 사용자 확인 (Team 3)
}

OWNER_TO_TEAM = {
    "Kim Sung Hoon": "Team 1",
    "Oh Sang Geol": "Team 1",
    "Baek Seung Chul": "Team 2",
    "Lee Garam": "Team 2",
    "Lim Yong Chul": "Team 3",
    "Yoon Dongjun": "Team 1",
    "Kim Byungwook": "Team 2",
    "Park Gookgi": "Team 3",
    "Jeong Ilyeong": "Team 3",
}
