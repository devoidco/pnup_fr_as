$(document).ready(function(){
    $("select#pilih_mode").on('change', function(){
        if (this.value == 0) {
            $("div#detail_mode").html("Choose Mode");
        } else if (this.value == 1) {
            $.ajax({
                url: "/check_data",
                success: function(result) {
                    $("div#detail_mode").html(result);
                }
            });
        } else if (this.value == 2) {
            $.ajax({
                url: "/enroll",
                success: function(result) {
                    $("div#detail_mode").html(result);
                }
            });
        } else if (this.value == 3) {
            $.ajax({
                url: "/absensi_index",
                success: function(result) {
                    $("div#detail_mode").html(result);
                }
            });
        }
    });
});