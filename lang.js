/* ============================================================
 * lang.js
 * 공통 다국어 사전 + 헬퍼.
 *  사용:
 *    AppLang.setLang('ko');
 *    AppLang.t('save');                 → '저장'
 *    AppLang.tx('confirmDelete', name)  → '"name" 정말 삭제하시겠습니까?'
 *
 * 화면별 추가 사전은 AppLang.merge({ key: { ko, en } }) 로 주입.
 * ============================================================ */
(function (root) {
  'use strict';

  const DICT = {
    // ── 공통 액션 ──
    save:           { ko: '저장',                 en: 'Save' },
    cancel:         { ko: '취소',                 en: 'Cancel' },
    edit:           { ko: '수정',                 en: 'Edit' },
    delete:         { ko: '삭제',                 en: 'Delete' },
    add:            { ko: '추가',                 en: 'Add' },
    close:          { ko: '닫기',                 en: 'Close' },
    confirm:        { ko: '확인',                 en: 'Confirm' },
    loginBtn:       { ko: '접속하기',             en: 'Log In' },
    logoutBtn:      { ko: '로그아웃',             en: 'Log Out' },
    export:         { ko: 'CSV 내보내기',         en: 'Export CSV' },

    // ── 알림 메시지 ──
    saveSuccess:    { ko: '저장되었습니다.',      en: 'Saved successfully.' },
    saveFail:       { ko: '저장에 실패했습니다.', en: 'Save failed.' },
    deleteSuccess:  { ko: '삭제되었습니다.',      en: 'Deleted.' },
    deleteFail:     { ko: '삭제에 실패했습니다.', en: 'Delete failed.' },
    updateSuccess:  { ko: '업데이트되었습니다.',  en: 'Updated.' },
    updateFail:     { ko: '업데이트에 실패했습니다.', en: 'Update failed.' },
    loadFail:       { ko: '데이터를 불러오지 못했습니다.', en: 'Failed to load data.' },
    targetSaveFail: { ko: '목표값 저장에 실패했습니다.', en: 'Failed to save target.' },
    confirmDelete:  { ko: '정말 삭제하시겠습니까?', en: 'Are you sure you want to delete this?' },

    // ── 검증 메시지 ──
    noAccount:      { ko: 'Account명(납품처)을 입력해주세요.', en: 'Please enter the Account name.' },
    noDealer:       { ko: 'Dealer Name 항목을 선택해주세요.', en: 'Please select a Dealer Name.' },
    noPrice:        { ko: 'Price(KRW)를 입력해주세요.', en: 'Please enter Price (KRW).' },
    invalidPrice:   { ko: 'Price(KRW)는 0 이상의 숫자여야 합니다.', en: 'Price (KRW) must be a non-negative number.' },
    noDeliveryDate: { ko: 'Delivery Date를 입력해주세요.', en: 'Please enter Delivery Date.' },

    // ── 상태/타입 ──
    statusACT:      { ko: 'ACT (납품완료)',       en: 'ACT (Delivered)' },
    statusPending:  { ko: 'Pending (납품예정)',   en: 'Pending (Scheduled)' },
    statusBackup:   { ko: 'Back up',              en: 'Back up' },
    statusMinal:    { ko: '미납',                 en: 'Unpaid' },

    // ── 공통 라벨 ──
    quarter:        { ko: '분기',                 en: 'Quarter' },
    team:           { ko: '팀',                   en: 'Team' },
    member:         { ko: '담당자',               en: 'Member' },
    product:        { ko: '제품',                 en: 'Product' },
    amount:         { ko: '금액',                 en: 'Amount' },
    count:          { ko: '건수',                 en: 'Count' },
    ratio:          { ko: '비율',                 en: 'Share' },
    target:         { ko: '목표',                 en: 'Target' },
    achievement:    { ko: '달성률',               en: 'Achievement' },
    cases:          { ko: '건',                   en: 'cases' },

    // ── CSV / 내보내기 ──
    exportFilter:   { ko: '내보내기 옵션',         en: 'Export Options' },
    exportAll:      { ko: '전체',                 en: 'All' },
    exportCurrent:  { ko: '현재 분기',            en: 'Current Quarter' },
    exportInclude:  { ko: 'Back up / 미납 포함',  en: 'Include Back up / Unpaid' },
  };

  let _lang = (typeof localStorage !== 'undefined' && localStorage.getItem('lang')) || 'ko';

  function setLang(lang) {
    _lang = (lang === 'en') ? 'en' : 'ko';
    try { localStorage.setItem('lang', _lang); } catch (e) {}
    if (typeof root !== 'undefined' && root.dispatchEvent) {
      root.dispatchEvent(new CustomEvent('app:langchange', { detail: { lang: _lang } }));
    }
  }
  function getLang() { return _lang; }
  function toggleLang() { setLang(_lang === 'ko' ? 'en' : 'ko'); return _lang; }

  function t(key) {
    const entry = DICT[key];
    if (!entry) return key;
    return entry[_lang] || entry.ko || key;
  }

  // 변수 치환: tx('confirmDeleteX', '홍길동') → "'홍길동' ..."
  function tx(key) {
    const args = Array.prototype.slice.call(arguments, 1);
    let s = t(key);
    args.forEach((a, i) => { s = s.replace('{' + i + '}', a); });
    return s;
  }

  // 화면별 사전 추가
  function merge(extraDict) {
    if (!extraDict) return;
    Object.keys(extraDict).forEach(k => { DICT[k] = extraDict[k]; });
  }

  root.AppLang = { setLang, getLang, toggleLang, t, tx, merge };
})(typeof window !== 'undefined' ? window : globalThis);
