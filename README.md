# 리팩토링 결과 — Sales Dashboard 코드 정리

업로드된 3개 파일(`index_password.html`, `dashboard_26.html`, `report.html`)에 대한
12개 항목 리팩토링이 완료된 결과입니다.

## 📁 파일 구성

| 파일                   | 역할                                          | 변경         |
|----------------------|---------------------------------------------|------------|
| `firebase-init.js`   | Firebase 초기화 단일 진실 공급원 (db, auth)            | **신규**     |
| `common-utils.js`    | 매출 집계 기준 / 검증 / ID 생성 / 토스트 / safeRun        | **신규**     |
| `lang.js`            | 공통 다국어 사전 + helper                          | **신규**     |
| `index_password.html`| 메인 Dashboard (입력 + 집계)                      | **수정**     |
| `dashboard_26.html`  | Detail Report                               | **수정**     |
| `report.html`        | 대표님 보고용 Sales Progress                      | **수정 (전면)** |

## ⚠️ 호스팅 메모

3개 HTML과 3개 JS 모두 **같은 디렉터리에 두어야 합니다.**
모든 HTML은 `<script src="firebase-init.js">` 등을 상대 경로로 참조합니다.

---

## ✅ 항목별 변경 내역

### 1) 보고서 보안 (가장 시급)
- `report.html`의 하드코딩 비밀번호 + `localStorage adminAuth` 우회 가능 방식 **완전 제거**.
- Firebase Auth(`signInWithEmailAndPassword`)로 통일.
- 미로그인 시 로그인 폼, 로딩 중 스피너, `currentUser.email` 표시.
- `dashboard_26.html`도 `auth.onAuthStateChanged` 게이트 추가
  → 로그인 안 한 상태에서는 데이터를 fetch하지 않고 안내 화면만 표시.

### 2) Firebase 설정 / 공통 코드 분리
- 3개 파일에 흩어져 있던 `firebaseConfig` → `firebase-init.js` 한 곳.
- `window.db`, `window.auth` 로 노출, 중복 init 방지(`firebase.apps.length` 체크).
- 공통 로직(`common-utils.js`)에 모듈화:
  - 매출 집계 기준 (`isCountedForRevenue`, `filterRevenueRows`)
  - 입력 검증 (`validateSalesEntry`)
  - ID 생성 (`generateId` — UUID/fallback)
  - 분기·날짜 유틸 (`parseQuarter`, `getMonthIdx`, `getWeekIdx`)
  - 포맷터 (`fmt억`, `fmtKRW`, `fmtUSD` 등)
  - 토스트 (`showToast`)
  - 안전 실행 (`safeRun`: try/catch + 토스트 묶음)

### 3) ACT / Pending / Backup / 미납 매출 기준 통일
**단일 진실 공급원**: `AppCommon.filterRevenueRows()`
- 포함: `status === 'ACT'`, `status === 'Pending'`
- 제외: `status === 'Back up'`, `status === '미납'`

| 파일                 | Before                                       | After                            |
|--------------------|---------------------------------------------|----------------------------------|
| index_password     | 인라인 `d.status === 'Pending'│'ACT'`           | `filterRevenueRows(currentQData)` |
| dashboard_26       | **`ACT│Pending│FCST`** ← 비일관                | `filterRevenueRows(...)`          |
| report             | **`shipConfirm === 'Yes'`** ← 완전히 다른 기준    | `filterRevenueRows(...)`          |

→ 3개 화면의 매출/예상치/Top Performer 숫자가 **이제 같은 기준으로 일치**.

### 4) 보고서 권한 통일
- 메인/Detail/보고서 모두 Firebase Auth 사용.
- 모든 로그인 사용자 접근 가능 (요청 사양).
- (확장 시 Firestore `users/{uid}.role` 추가만 하면 됨)

### 5) 데이터 저장 검증 강화
`common-utils.js`의 `validateSalesEntry()`로 통일 검증:
- account, dealerName (기존)
- **status** (ACT/Pending/Back up/미납 중 하나)
- **salesType** (Direct/Indirect 중 하나)
- **priceKRW**: 빈값 / 문자 / 음수 차단 (`Number.isNaN`, `< 0`)
- **deliveryDate**: ACT/Pending 일 때 필수, `YYYY-MM-DD` 형식 체크
- **quarter / member / team** 컨텍스트 검증

검증 실패 시 `alert()` 대신 토스트 표시.

### 6) ID 생성 방식 개선
- `Date.now()` → `crypto.randomUUID()` (지원 안 되는 환경은 `Date.now() + Math.random()` fallback)
- 동시 저장 시 ID 충돌 가능성 사실상 0.
- `payload.updatedAt = new Date().toISOString()` 도 같이 저장.
- 기존 데이터(숫자 id)와도 호환: `doc(id.toString())` 그대로 동작.

### 7) CSV Export 보완
입력 폼 사이드바의 "CSV Export" 버튼이 옵션 패널을 토글:
- **범위**: 전체 / 현재 분기 / 현재 분기 + 담당자
- **Back up / 미납 포함 여부** (기본 OFF → ACT+Pending 만)
- 파일명: `Sales_<scope>_<ACT-Pending|with-backup>_YYYY-MM-DD.csv`
- 결과: 토스트로 "N건 내보내기 완료".

### 8) 다국어 로직 정리
- `lang.js`에 공통 사전 (`AppLang.t / tx / setLang / toggleLang`).
- 화면별 사전은 `AppLang.merge({...})` 로 추가 (중복 없음).
- 추후 보고서·Detail Report의 인라인 `T = {...}`도 점진적으로 이쪽으로 이관 가능.

### 9) 실시간 구독 최적화
- `db.collection("sales").onSnapshot(...)` → **`where("quarter","==",selectedQuarter)`** 로 query 제한.
- 분기 전환 시 자동 재구독 (`useEffect` 의존성에 `selectedQuarter` 추가).
- 전체 sales 수가 늘어도 trade size가 분기 단위로 고정되어 가벼움.

### 10) 보고서 숫자 기준 통일
- `report.html` / `dashboard_26.html` 기본 분기 모두 **`2026 Q2`** 로 통일.
- 메인 Dashboard에서 보고서 새 창 열 때 `?quarter=...` 파라미터 전달.

### 11) UI/UX 보완
- **토스트 시스템**: 저장/삭제/업데이트/실패 모두 화면 하단에 표시 (alert 대체).
- 보고서 로그인 화면, 인증 로딩 스피너 추가.
- 보고서 헤더에 현재 로그인 이메일 노출.
- 보고서 하단 "매출 집계 기준: ACT + Pending. (Back up / 미납은 제외)" 명시.

### 12) 운영 안정성
- 모든 `db.collection(...).set/delete/update` 호출에 `.catch` 또는 `safeRun`.
- 모든 `onSnapshot` 두 번째 인자에 에러 콜백 → 콘솔 로깅 + 토스트.
- `URL.revokeObjectURL` 추가로 메모리 누수 방지 (CSV 다운로드).

---

## 🔧 후속으로 권장하는 작업 (이번 범위 외)

1. **Firestore Security Rules 잠그기** — Auth 적용했으니 이제 룰에서 인증되지 않은 read/write 차단.
   ```
   match /sales/{doc}    { allow read, write: if request.auth != null; }
   match /targets/{doc}  { allow read, write: if request.auth != null; }
   match /settings/{doc} { allow read, write: if request.auth != null; }
   ```
2. **role 기반 권한** — 향후 `users/{uid}` 컬렉션에 `role` 필드 추가하면, 보고서 접근을 admin만으로 제한 가능.
3. **모바일 테이블 가로 스크롤 개선** — 현재는 `overflow-x:auto` 중심. 카드형 mobile view 추가 검토.
4. **레거시 데이터 정리** — `shipConfirm` 필드를 사용했던 과거 데이터가 있다면, status 표준 4종으로 마이그레이션 1회 필요.
