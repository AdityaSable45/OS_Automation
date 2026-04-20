import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:8000';

  /// Returns true when the backend health-check endpoint responds 200.
  static Future<bool> checkConnection() async {
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/'))
          .timeout(const Duration(seconds: 3));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// POSTs a command and returns the parsed JSON response.
  static Future<Map<String, dynamic>> sendCommand(String text) async {
    try {
      final response = await http
          .post(
            Uri.parse('$baseUrl/execute'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'text': text}),
          )
          .timeout(const Duration(seconds: 15));

      final data = jsonDecode(response.body);
      if (data is Map<String, dynamic>) {
        return data;
      }

      return {'result': response.body};
    } catch (e) {
      return {
        'result': 'Error: Could not connect to backend ($e)',
        'options': [],
      };
    }
  }
}