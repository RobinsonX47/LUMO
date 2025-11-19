// Minimal UI helpers: modal and simple interactions
document.addEventListener('DOMContentLoaded', function(){
  // placeholder for future modal implementation
  window.ui = {
    openModal: function(id){
      const el = document.getElementById(id);
      if(el) el.style.display = 'block';
    },
    closeModal: function(id){
      const el = document.getElementById(id);
      if(el) el.style.display = 'none';
    }
  };
});
