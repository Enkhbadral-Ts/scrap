window.suggest = function() {
  var val = $('#query').val();
  var type = $("#type").val();
  if(val.length > 1) {
    $.get("/search/search?query=" + val + "&type=" + type, function(data, status){
      $("#autocomplete").html(data);
    });
  }
  else {
    $("#autocomplete").html('');
  }
}

$(function() {
//document.addEventListener('turbolinks:load', () => {
  // Sticky nav
  $(window).on('scroll', function () {
    if ($(this).scrollTop() > 1) {
      $('.header').addClass("sticky");
    } else {
      $('.header').removeClass("sticky");
    }
  });

  // Rotate icons
  $(".main_categories a").on('mouseenter', function() {
    $(this).find("h4").toggleClass("rotate-x");}
  );

});
