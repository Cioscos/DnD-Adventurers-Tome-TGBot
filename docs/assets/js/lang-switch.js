(function () {
  var STORAGE_KEY = 'dndbot-lang';

  function setLang(lang) {
    document.querySelectorAll('.lang-en').forEach(function (el) {
      el.style.display = lang === 'en' ? '' : 'none';
    });
    document.querySelectorAll('.lang-it').forEach(function (el) {
      el.style.display = lang === 'it' ? '' : 'none';
    });
    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });
    localStorage.setItem(STORAGE_KEY, lang);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var saved = localStorage.getItem(STORAGE_KEY) || 'en';
    setLang(saved);

    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        setLang(this.dataset.lang);
      });
    });
  });
})();
