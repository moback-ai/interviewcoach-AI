function handler(event) {
  var request = event.request;
  var host = request.headers.host.value;
  if (host === 'ugaanlabs.ai') {
    var uri = request.uri;
    var parts = [];
    for (var key in request.querystring) {
      if (request.querystring[key].multiValue) {
        request.querystring[key].multiValue.forEach(function (v) {
          parts.push(key + '=' + v.value);
        });
      } else {
        parts.push(key + '=' + request.querystring[key].value);
      }
    }
    var location = 'https://www.ugaanlabs.ai' + uri;
    if (parts.length > 0) {
      location += '?' + parts.join('&');
    }
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: { location: { value: location } },
    };
  }
  return request;
}
