<?
$errors = array();
$input = array();

if ($_SERVER['REQUEST_METHOD'] == "POST") {
  $input = $_POST;
  handle_post();
}
else {
  handle_get();
}

function handle_get() {
  render_header();
  render_body();
  include_javascripts();
  render_footer();
}

function handle_post() {
  global $errors, $input;
  global $_POST;

  $url = "http://lsp-signup.anandology.com/signup_api";

  $response = json_post($url, prepare_payload($_POST));
  if ($response == NULL) {
    $errors["*"] = "Unexpected error in processing the request. Please try again after some time.";
    return handle_get();
  }
  elseif ($response['status'] != 'ok') {
    $errors = $response['errors'];
    return handle_get();
  }
  else {
    return thankyou();
  }
}

function prepare_payload($params) {
  $payload = "";
  foreach ($params as $k => $v) 
    $payload.=$k.'='.urlencode($v).'&';
  rtrim($payload, '&');
  return $payload;
}

function json_post($url, $payload) {
    $c = curl_init($url);
    curl_setopt($c, CURLOPT_RETURNTRANSFER, TRUE);
    curl_setopt($c, CURLOPT_POST, TRUE);
    curl_setopt($c, CURLOPT_POSTFIELDS, $payload);
    $content = curl_exec($c);
    $response = curl_getinfo($c);
    curl_close($c);

    if ($response['http_code'] != 200)
      return NULL;
    return json_decode($content, TRUE);
}

function thankyou() {
  ?>
    <div class="container">
        <div>
            <h1>Thank You!</h1>
            <div>
              <p>Thank you for stepping up to volunteer for Loksatta.</p> 
              <p>We'll get in touch with you shortly.</p>
            </div>
        </div>
    </div>
<?
}

function render_field($name, $label, $placeholder, $help=null, $help2=null, $value="") {
  global $errors, $input;
  $has_error = array_key_exists($name, $errors);
  $value = array_key_exists($name, $input) ? $input[$name] : "";
  ?>
    <div class="form-group <?= $has_error ? 'has-error' : '' ?> ">
      <label for="<?= $name ?>"><?= $label ?></label>
      <input type="text" 
             class="form-control" 
             name="<?= $name ?>" 
             id="<?= $name ?>" 
             placeholder="<?= $placeholder ?>"
             value="<?= $value ?>" />
        <? if ($has_error) { ?>
          <ul class="help-block list-unstyled">
              <li><?= $errors[$name] ?></li>
          </ul> 
        <? } ?>
        <? if ($help) { ?>
            <p class="help-block help-first"><?= $help ?></p>
        <? } ?>
        <? if ($help2) { ?>
            <p class="help-block help-second" style="display: none;"><?= $help2 ?></p>
        <? } ?>
    </div>
  <?
}

function render_body() {
  global $errors;
?>
<div class="container-fluid" style="height: 100%;">
    <div class="row" style="height: 100%;">
        <div class="col-md-4">
            <div id="panel2">
              <h2>Booth Agent Registration</h2>

              <p>Sign up a polling booth agent for Loksatta.</p>

              <? if (array_key_exists("*", $errors)) { ?>
                <div class="alert alert-danger">
                  <?= $errors["*"] ?>
                </div>
              <? } ?>

                <form class="form" id="signup-form" method="POST" role="form">
                  <? render_field("name", "Name", "Enter your name"); ?>
                  <? render_field("phone", "Phone Number", "Enter your phone number"); ?>
                  <? render_field("email", "E-mail Address", "Enter your e-mail address"); ?>
                  <? render_field("voterid", "Voter ID", "Enter your voter ID"); ?>
                  <? render_field("address", "Locality", "Select your locality", 
                      "Please pick a locality from the dropdown so that we can identify your assembly constituency automatically.",
                      '<i class="fa fa-spinner fa-spin"></i> Please wait while we discover your assembly constituency from the location.'
                      ); 
                  ?>
                  <input type="hidden" id="ward" name="ward" value=""/>                  
                  <div class="address-details alert alert-info" style="display: none;">
                    The above locality falls in:<br/><br/>
                    <div>
                    <div><span class="ac">Kukatpally</span> <small>Assembly Constituency</small></div>
                    <div><span class="pc">Malkajgiri</span> <small>Parliamentary Constituency</small></div>
                    </div><br/>
                    <div><small>If you think it is not correct, please correct the locality in the above text box.</small></div>
                  </div>
                  <div class="address-error alert alert-danger" style="display: none;">
                    <strong>Oops!</strong> The selected locality doesn't seem to be in Andhra Pradesh.. Are you sure that is in Andhra Pradesh?
                  </div>                  
                  <button type="submit" id="signup-button" class="btn btn-primary">Sign Up</button>
                </form>
            </div>
        </div>
        <div class="col-md-8" style="height: 100%">
            <div id="map-canvas" style="height: 100%; min-height: 570px;"></div>
        </div>
    </div>
</div>
<?
}

function include_javascripts() {
?>

<script src="https://maps.googleapis.com/maps/api/js?v=3.exp&sensor=false&libraries=places"></script>
<script src="https://geosearch-anandology.rhcloud.com/js/jquery-geosearch.js"></script>

<script type="text/javascript">
function locate(location, callback) {
    $("#address").parent().find(".help-first").hide();
    $("#address").parent().find(".help-second").show();

    //$(".address-spinner").show();
    var url = "https://geosearch-anandology.rhcloud.com/geosearch?lat=" + location.A + "&lon=" + location.k;
    $.getJSON(url, function(response) {
        console.log(response && response.result.st_name == "AP");
        $("#address").parent().find(".help-second").hide();
        if (response && response.result.st_name == "AP") {
          var result  = response.result;
          console.log(result);
          $(".address-error").hide();      
          $(".address-details").show();            
          $(".address-details .ward").parent().hide();
          $(".address-details .ac").html(result.ac_name);
          $(".address-details .pc").html(result.pc_name);
          $("input#ward").val(result.ac_key);
        }
        else {
          $(".address-error").show();      
          $(".address-details").hide();      
        }
        callback();
        console.log(response);
    });
}

function initialize() {
  var latlng = new google.maps.LatLng(17.450888, 78.5291706);
  var mapOptions = {
    center: latlng,
    zoom: 12
  };
  var map = new google.maps.Map(document.getElementById('map-canvas'),
    mapOptions);

  var input = /** @type {HTMLInputElement} */(
      document.getElementById('address'));

  /*
  var types = document.getElementById('type-selector');
  map.controls[google.maps.ControlPosition.TOP_LEFT].push(input);
  map.controls[google.maps.ControlPosition.TOP_LEFT].push(types);
 */

  var autocomplete = new google.maps.places.Autocomplete(input);
  //autocomplete.bindTo('bounds', map);

  var infowindow = new google.maps.InfoWindow();
  var marker = new google.maps.Marker({
    map: map
  });

  google.maps.event.addListener(autocomplete, 'place_changed', function() {
    infowindow.close();
    marker.setVisible(false);
    var place = autocomplete.getPlace();
    if (!place.geometry) {
      return;
    }

    locate(place.geometry.location, function() {
      // If the place has a geometry, then present it on a map.
      if (place.geometry.viewport) {
        map.fitBounds(place.geometry.viewport);
      } else {
        map.setCenter(place.geometry.location);
        map.setZoom(17);  // Why 17? Because it looks good.
      }
      marker.setIcon(/** @type {google.maps.Icon} */({
        url: place.icon,
        size: new google.maps.Size(71, 71),
        origin: new google.maps.Point(0, 0),
        anchor: new google.maps.Point(17, 34),
        scaledSize: new google.maps.Size(35, 35)
      }));
      marker.setPosition(place.geometry.location);
      marker.setVisible(true);

      var address = '';
      if (place.address_components) {
        address = [
          (place.address_components[0] && place.address_components[0].short_name || ''),
          (place.address_components[1] && place.address_components[1].short_name || ''),
          (place.address_components[2] && place.address_components[2].short_name || '')
        ].join(' ');
      }

      infowindow.setContent('<div><strong>' + place.name + '</strong><br>' + address);
      infowindow.open(map, marker);
    });
  });
  // Sets a listener on a radio button to change the filter type on Places
  // Autocomplete.
  function setupClickListener(id, types) {
    var radioButton = document.getElementById(id);
    google.maps.event.addDomListener(radioButton, 'click', function() {
      autocomplete.setTypes(types);
    });
  }

  setupClickListener('changetype-all', []);
  setupClickListener('changetype-establishment', ['establishment']);
  setupClickListener('changetype-geocode', ['geocode']);
}

google.maps.event.addDomListener(window, 'load', initialize);

$(function() {

  // disable form submit on enter
  $('#signup-form').bind("keyup keypress", function(e) {
    var code = e.keyCode || e.which; 
    if (code  == 13) {               
      e.preventDefault();
      return false;
    }
  });
});

</script>
<?
}

function render_header() {
  ?>
    <link rel="stylesheet" href="//netdna.bootstrapcdn.com/bootstrap/3.0.3/css/bootstrap.min.css">
    <link rel="stylesheet" href="//netdna.bootstrapcdn.com/bootstrap/3.0.3/css/bootstrap-theme.min.css">
    <link rel="stylesheet" href="//netdna.bootstrapcdn.com/font-awesome/4.0.3/css/font-awesome.css">

    <script src="//ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js"></script>

<!-- HTML5 shim and Respond.js IE8 support of HTML5 elements and media queries -->
<!--[if lt IE 9]>
  <script src="https://oss.maxcdn.com/libs/html5shiv/3.7.0/html5shiv.js"></script>
  <script src="https://oss.maxcdn.com/libs/respond.js/1.4.2/respond.min.js"></script>
<![endif]-->

    <style>
      html, body, #map-canvas {
        height: 100%;
        margin: 0px;
        padding: 0px
      }
      #panel2 {
        padding: 0px 0px 20px 20px;
      }
      .gray {
        color: #555;
      }
      .coordinator {
        margin: 20px;
      }

      div.section {
        margin: 20px 0px;
      }
      p.pre {
        white-space: pre;
      }

      nav.navbar {
        margin-bottom: 0px;
      }

      .address-details {
        margin: 5px 0px 15px 0px;
      }

      .address-details small {
        text-size: 0.9em;
      }

      .controls {
        margin-top: 16px;
        border: 1px solid transparent;
        border-radius: 2px 0 0 2px;
        box-sizing: border-box;
        -moz-box-sizing: border-box;
        height: 32px;
        outline: none;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
      }

      #pac-input {
        background-color: #fff;
        padding: 0 11px 0 13px;
        width: 400px;
        font-family: Roboto;
        font-size: 15px;
        font-weight: 300;
        text-overflow: ellipsis;
      }

      #pac-input:focus {
        border-color: #4d90fe;
        margin-left: -1px;
        padding-left: 14px;  /* Regular padding-left + 1. */
        width: 401px;
      }

      .pac-container {
        font-family: Roboto;
      }

      #type-selector {
        color: #fff;
        background-color: #4d90fe;
        padding: 5px 11px 0px 11px;
      }

      #type-selector label {
        font-family: Roboto;
        font-size: 13px;
        font-weight: 300;
      }

      /* overwrite margin of the page */
      .no-sidebars #content {
        margin: 0 !important;
      }

      #main {
        padding: 0 !important;
      }

      #content-wrap {
        margin: 0px !important;
      }      
    </style>
  <?
}

function render_footer() {
  ?>
  <?
}
?>