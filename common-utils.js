/* ============================================================
 * common-utils.js
 * 공통 상수 / 집계 기준 / 검증 / 포맷터
 *
 * 핵심: 매출/예상치 집계 기준은 단 하나, isCountedForRevenue()로 통일.
 *   - 포함:  status === 'ACT'    (납품 완료)
 *   - 포함:  status === 'Pending'(납품 예정)
 *   - 제외:  status === 'Back up'(백업)
 *   - 제외:  status === '미납'   (미납)
 * 모든 화면(dashboard / report / detail)이 이 함수를 사용해야 한다.
 * ============================================================ */
(function (root) {
  'use strict';

  // ── 1. 상태 상수 ──────────────────────────────────────────
  const STATUS = Object.freeze({
    ACT:     'ACT',
    PENDING: 'Pending',
    BACKUP:  'Back up',   // 매출 제외
    MINAL:   '미납'       // 매출 제외
  });

  const ALL_STATUS = [STATUS.ACT, STATUS.PENDING, STATUS.BACKUP, STATUS.MINAL];
  const REVENUE_STATUS = [STATUS.ACT, STATUS.PENDING];

  function isCountedForRevenue(row) {
    if (!row) return false;
    return row.status === STATUS.ACT || row.status === STATUS.PENDING;
  }

  /**
   * 매출 집계 기준 필터.
   * @param {Array} rows  원본 데이터
   * @param {Object} [opts]
   * @param {boolean} [opts.includeBackup=false]  Back up 포함 여부
   * @param {boolean} [opts.includeMinal=false]   미납 포함 여부
   * @returns {Array}
   */
  function filterRevenueRows(rows, opts) {
    opts = opts || {};
    return (rows || []).filter(r => {
      if (!r || !r.status) return false;
      if (r.status === STATUS.ACT || r.status === STATUS.PENDING) return true;
      if (opts.includeBackup && r.status === STATUS.BACKUP) return true;
      if (opts.includeMinal  && r.status === STATUS.MINAL)  return true;
      return false;
    });
  }

  // ── 2. ID 생성 ────────────────────────────────────────────
  /**
   * 충돌 가능성을 최소화한 ID 생성기.
   * crypto.randomUUID() 사용, 미지원 환경은 timestamp+random fallback.
   */
  function generateId() {
    try {
      if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
      }
    } catch (e) {}
    // Fallback
    return 'id-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
  }

  // ── 3. 입력 검증 ──────────────────────────────────────────
  const VALID_STATUS  = new Set(ALL_STATUS);
  const VALID_SALES_TYPE = new Set(['Direct', 'Indirect']);

  /**
   * 매출 입력 검증. 통과하면 { ok: true }, 실패시 { ok: false, message }.
   *
   * @param {Object} form
   * @param {Object} [ctx]  추가 검증용 컨텍스트(quarter, member, team)
   */
  function validateSalesEntry(form, ctx) {
    if (!form) return { ok: false, message: '입력값이 없습니다.' };

    // 필수 텍스트 필드
    if (!form.account || !String(form.account).trim()) {
      return { ok: false, message: 'Account명(납품처)을 입력해주세요.' };
    }
    if (!form.dealerName || !String(form.dealerName).trim()) {
      return { ok: false, message: 'Dealer Name 항목을 선택해주세요.' };
    }

    // status
    if (!form.status || !VALID_STATUS.has(form.status)) {
      return { ok: false, message: '상태(Status)가 유효하지 않습니다.' };
    }

    // salesType
    if (!form.salesType || !VALID_SALES_TYPE.has(form.salesType)) {
      return { ok: false, message: 'Sales Type을 선택해주세요. (Direct / Indirect)' };
    }

    // priceKRW: 숫자 / 0 이상 / 빈값 불가
    if (form.priceKRW === '' || form.priceKRW === null || form.priceKRW === undefined) {
      return { ok: false, message: 'Price(KRW)를 입력해주세요.' };
    }
    const priceNum = Number(form.priceKRW);
    if (Number.isNaN(priceNum)) {
      return { ok: false, message: 'Price(KRW)는 숫자만 입력 가능합니다.' };
    }
    if (priceNum < 0) {
      return { ok: false, message: 'Price(KRW)는 0 이상이어야 합니다.' };
    }

    // deliveryDate (YYYY-MM-DD)
    // ACT/Pending은 날짜 필수, Back up/미납은 선택 (실제 미정일 수 있음)
    const isRevenue = form.status === STATUS.ACT || form.status === STATUS.PENDING;
    if (isRevenue) {
      if (!form.deliveryDate) {
        return { ok: false, message: 'Delivery Date를 입력해주세요.' };
      }
      if (!/^\d{4}-\d{2}-\d{2}$/.test(form.deliveryDate)) {
        return { ok: false, message: 'Delivery Date 형식이 올바르지 않습니다. (YYYY-MM-DD)' };
      }
    }

    // 컨텍스트 검증
    if (ctx) {
      if (!ctx.quarter)   return { ok: false, message: '분기(Quarter)가 선택되지 않았습니다.' };
      if (!ctx.member)    return { ok: false, message: '담당자(Member)가 선택되지 않았습니다.' };
      if (!ctx.team)      return { ok: false, message: '팀(Team)이 선택되지 않았습니다.' };
    }

    return { ok: true };
  }

  // ── 4. 날짜 / 분기 유틸 ───────────────────────────────────
  /** "2026 Q1" → { year: 2026, q: 'Q1', months: [1,2,3] } */
  function parseQuarter(qStr) {
    if (!qStr || typeof qStr !== 'string') return null;
    const parts = qStr.split(' ');
    const year = parseInt(parts[0], 10);
    const q = parts[1] || 'Q1';
    const QM = { Q1: [1, 2, 3], Q2: [4, 5, 6], Q3: [7, 8, 9], Q4: [10, 11, 12] };
    return { year, q, months: QM[q] || [1, 2, 3] };
  }

  function getMonthIdx(dateStr) {
    if (!dateStr) return -1;
    const m = parseInt(String(dateStr).split('-')[1], 10);
    return Number.isNaN(m) ? -1 : m;
  }

  function getWeekIdx(dateStr) {
    if (!dateStr) return 0;
    const d = parseInt(String(dateStr).split('-')[2], 10);
    if (Number.isNaN(d)) return 0;
    if (d <= 7)  return 1;
    if (d <= 14) return 2;
    if (d <= 21) return 3;
    if (d <= 28) return 4;
    return 5;
  }

  // ── 5. 포맷터 ─────────────────────────────────────────────
  const fmt억 = v => v >= 100000000
    ? `₩${(v / 100000000).toFixed(2)}억`
    : `₩${Math.round(v / 10000).toLocaleString()}만`;
  const fmtKRW = v => `₩ ${(v || 0).toLocaleString()}`;
  const fmtUSD = v => v >= 1000000
    ? `$${(v / 1000000).toFixed(2)}M`
    : `$${Math.round(v / 1000).toLocaleString()}K`;
  const fmtUSDFull = v => `$ ${Math.round(v || 0).toLocaleString()}`;

  // ── 6. 토스트 알림 (저장/삭제/실패 표시) ─────────────────
  function ensureToastContainer() {
    let c = document.getElementById('__app_toast_container');
    if (c) return c;
    c = document.createElement('div');
    c.id = '__app_toast_container';
    c.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
    document.body.appendChild(c);
    return c;
  }
  /**
   * showToast(message, type)
   *   type: 'success' | 'error' | 'info'
   */
  function showToast(message, type) {
    type = type || 'info';
    const container = ensureToastContainer();
    const palette = {
      success: { bg: '#16a34a', fg: '#fff' },
      error:   { bg: '#dc2626', fg: '#fff' },
      info:    { bg: '#1e293b', fg: '#fff' }
    }[type] || { bg: '#1e293b', fg: '#fff' };

    const el = document.createElement('div');
    el.style.cssText = `
      pointer-events:auto;
      background:${palette.bg};
      color:${palette.fg};
      padding:10px 18px;
      border-radius:10px;
      font-size:13px;
      font-weight:600;
      box-shadow:0 8px 24px rgba(0,0,0,0.18);
      opacity:0;
      transform:translateY(8px);
      transition:opacity .2s ease, transform .2s ease;
      max-width:90vw;
      text-align:center;
    `;
    el.textContent = message;
    container.appendChild(el);

    requestAnimationFrame(() => {
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    });

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 250);
    }, 2400);
  }

  // ── 7. 안전한 Firestore wrapper ───────────────────────────
  /**
   * try/catch + 토스트 표시까지 묶은 헬퍼.
   *   const ok = await safeRun(() => db.collection(...).set(...), { successMsg, errorMsg });
   */
  async function safeRun(fn, opts) {
    opts = opts || {};
    try {
      const result = await fn();
      if (opts.successMsg) showToast(opts.successMsg, 'success');
      return { ok: true, value: result };
    } catch (err) {
      console.error('[safeRun]', err);
      const msg = (opts.errorMsg || '작업에 실패했습니다.') + (err && err.message ? `\n(${err.message})` : '');
      showToast(msg, 'error');
      return { ok: false, error: err };
    }
  }

  // ── export ────────────────────────────────────────────────
  root.AppCommon = {
    STATUS,
    ALL_STATUS,
    REVENUE_STATUS,
    isCountedForRevenue,
    filterRevenueRows,
    generateId,
    validateSalesEntry,
    parseQuarter,
    getMonthIdx,
    getWeekIdx,
    fmt억,
    fmtKRW,
    fmtUSD,
    fmtUSDFull,
    showToast,
    safeRun
  };
})(typeof window !== 'undefined' ? window : globalThis);
