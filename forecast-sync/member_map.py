# Salesforce Opportunity Owner(영문 풀네임) -> sales-dashboard의 member 코드 / team 매핑.
# Firestore settings/layout.teams 에 등록된 실제 멤버 기준(2026-07-30 확인):
#   Team 1: Kim SH, Oh SG, Yoon DJ
#   Team 2: Baek SC, Lee GR, Kim BW
#   Team 3: Lim YC, GG Park
# Kim BW / GG Park 의 Salesforce Owner 풀네임은 아직 확인되지 않아 비어 있음 -
# 해당 이름의 Opportunity가 나타나면 스크립트가 경고하고 건너뛰므로, 그때 아래 dict에 추가할 것.

OWNER_TO_MEMBER = {
    "Kim Sung Hoon": "Kim SH",
    "Oh Sang Geol": "Oh SG",
    "Baek Seung Chul": "Baek SC",
    "Lee Garam": "Lee GR",
    "Lim Yong Chul": "Lim YC",
    "Yoon Dongjun": "Yoon DJ",
}

OWNER_TO_TEAM = {
    "Kim Sung Hoon": "Team 1",
    "Oh Sang Geol": "Team 1",
    "Baek Seung Chul": "Team 2",
    "Lee Garam": "Team 2",
    "Lim Yong Chul": "Team 3",
    "Yoon Dongjun": "Team 1",
}
