/* ============================================================
 * firebase-init.js
 * 모든 화면에서 공통으로 사용하는 Firebase 초기화 모듈
 * 사용법: <script src="firebase-init.js"></script>
 *   - window.firebaseConfig
 *   - window.db        (Firestore)
 *   - window.auth      (Firebase Auth)
 * ============================================================ */
(function () {
  'use strict';

  const firebaseConfig = {
    apiKey: "AIzaSyDpdX6I7fkE1m9jQDARg5l4Skv3vhD7iyI",
    authDomain: "sales-dashboard-d0d13.firebaseapp.com",
    projectId: "sales-dashboard-d0d13",
    storageBucket: "sales-dashboard-d0d13.firebasestorage.app",
    messagingSenderId: "870275096697",
    appId: "1:870275096697:web:cd7373b77358681e21b4a8",
    measurementId: "G-K5G6BMNBX9"
  };

  if (typeof firebase === 'undefined') {
    console.error('[firebase-init] firebase SDK가 로드되어 있지 않습니다. firebase-app.js를 먼저 포함하세요.');
    return;
  }

  if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
  }

  window.firebaseConfig = firebaseConfig;
  window.db = firebase.firestore();

  // firebase-auth.js가 포함된 경우만 auth 활성화
  if (typeof firebase.auth === 'function') {
    window.auth = firebase.auth();
  } else {
    window.auth = null;
  }
})();
