import 'dart:async';
import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';
import '../models/log_entry.dart';
import '../services/api_service.dart';
import '../widgets/terminal_log.dart';
import '../widgets/command_input.dart';
import '../widgets/quick_commands.dart';
import 'workflow_screen.dart';   // ✅ Aditya — workflow navigation

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  // ── controllers & state ─────────────────────────────────────────
  final TextEditingController _inputCtrl = TextEditingController();
  final FocusNode _focusNode = FocusNode();
  final ScrollController _scrollCtrl = ScrollController();
  final List<LogEntry> _logs = [];

  bool _isProcessing = false;
  bool _isConnected = false;
  bool _isListening = false;

  // ── speech ──────────────────────────────────────────────────────
  final SpeechToText _speech = SpeechToText();
  bool _speechAvailable = false;
  Timer? _silenceTimer;

  // ── connection retry ────────────────────────────────────────────
  Timer? _retryTimer;

  // ── clock ticker ────────────────────────────────────────────────
  Timer? _clockTimer;
  String _clockStr = '';

  // ── top bar glow animation ──────────────────────────────────────
  late final AnimationController _glowCtrl;
  late final Animation<double> _glowAnim;

  // ────────────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();

    _glowCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);
    _glowAnim = Tween<double>(begin: 0.4, end: 1.0).animate(_glowCtrl);

    _updateClock();
    _clockTimer =
        Timer.periodic(const Duration(seconds: 1), (_) => _updateClock());

    _initSpeech();
    _checkConnection(isStartup: true);
    _retryTimer =
        Timer.periodic(const Duration(seconds: 5), (_) => _retryIfNeeded());
  }

  @override
  void dispose() {
    _glowCtrl.dispose();
    _inputCtrl.dispose();
    _focusNode.dispose();
    _scrollCtrl.dispose();
    _silenceTimer?.cancel();
    _retryTimer?.cancel();
    _clockTimer?.cancel();
    super.dispose();
  }

  // ── helpers ─────────────────────────────────────────────────────

  void _updateClock() {
    final now = DateTime.now();
    setState(() {
      _clockStr =
          '${now.hour.toString().padLeft(2, '0')}:'
          '${now.minute.toString().padLeft(2, '0')}:'
          '${now.second.toString().padLeft(2, '0')}';
    });
  }

  void _addLog(LogType type, String message) {
    setState(() => _logs.add(LogEntry.now(type: type, message: message)));
    Future.delayed(const Duration(milliseconds: 60), _scrollToBottom);
  }

  void _scrollToBottom() {
    if (_scrollCtrl.hasClients) {
      _scrollCtrl.animateTo(
        _scrollCtrl.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    }
  }

  // ── connection ──────────────────────────────────────────────────

  Future<void> _checkConnection({bool isStartup = false}) async {
    final ok = await ApiService.checkConnection();
    final wasConnected = _isConnected;
    setState(() => _isConnected = ok);

    if (isStartup) {
      _addLog(LogType.sys, '⚡ FlowForge AI initialized');
      if (ok) {
        _addLog(LogType.success, '🔗 Backend connected at 127.0.0.1:8000');
        _addLog(LogType.sys, '💬 Type or speak a command to begin');
      } else {
        _addLog(LogType.error,
            '🔴 Backend not reachable — retrying every 5 s...');
      }
    } else if (ok && !wasConnected) {
      _addLog(LogType.success, '✅ Backend reconnected');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text(
              '✅ Backend reconnected',
              style: TextStyle(fontFamily: 'monospace'),
            ),
            backgroundColor: AppColors.successGreen.withValues(alpha: 0.85),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    }
  }

  void _retryIfNeeded() {
    if (!_isConnected) _checkConnection();
  }

  // ── speech ──────────────────────────────────────────────────────

  Future<void> _initSpeech() async {
    try {
      _speechAvailable = await _speech.initialize(
        onError: (_) => _stopListening(),
        onStatus: (status) {
          if (status == 'done' || status == 'notListening') {
            _stopListening();
          }
        },
      );
    } catch (e) {
      // Speech to text not available on this platform (e.g., Windows)
      _speechAvailable = false;
    }
    setState(() {});
  }

  Future<void> _toggleMic() async {
    if (_isListening) {
      _stopListening();
      return;
    }
    if (!_speechAvailable) {
      _addLog(LogType.error,
          '🎤 Speech recognition not available on this device');
      return;
    }
    setState(() {
      _isListening = true;
      _inputCtrl.clear();
    });

    await _speech.listen(
      onResult: (result) {
        setState(() => _inputCtrl.text = result.recognizedWords);
        _silenceTimer?.cancel();
        _silenceTimer = Timer(const Duration(milliseconds: 1500), () {
          _stopListening();
          if (_inputCtrl.text.trim().isNotEmpty) {
            _sendCommand(_inputCtrl.text.trim());
          }
        });
      },
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 3),
      listenOptions: SpeechListenOptions(
        partialResults: true,
        cancelOnError: true,
        listenMode: ListenMode.confirmation,
      ),
    );
  }

  void _stopListening() {
    _speech.stop();
    _silenceTimer?.cancel();
    setState(() => _isListening = false);
  }

  // ── command execution ────────────────────────────────────────────

  Future<void> _sendCommand(String cmd) async {
    cmd = cmd.trim();
    if (cmd.isEmpty || _isProcessing || !_isConnected) return;

    setState(() {
      _isProcessing = true;
      _inputCtrl.clear();
    });

    _addLog(LogType.cmd, '\$ $cmd');
    _addLog(LogType.sys, 'Executing command...');

    // ── Project creation warning — may take 30-60 seconds ────────
    final bool isProjectCommand =
        cmd.contains('create') ||
        cmd.contains('build') ||
        cmd.contains('make');

    if (isProjectCommand) {
      _addLog(LogType.sys,
          '⏳ Creating project... this may take 30-60 seconds. Please wait.');
    }

    // ── Send to backend — response is a full dict ─────────────────
    final Map<String, dynamic> response = await ApiService.sendCommand(cmd);

    final String result = response['result']?.toString() ?? 'No response';
    final List<dynamic> options = (response['options'] as List<dynamic>?) ?? [];

    // ── AI interpretation log ─────────────────────────────────────
    // Shows when AI rewrote the command e.g. "open my editor" → "open vscode"
    final String interpreted = response['interpreted']?.toString() ?? '';
    final String original = response['original']?.toString() ?? '';

    if (interpreted.isNotEmpty &&
        interpreted != original &&
        interpreted.toLowerCase() != cmd.toLowerCase()) {
      _addLog(
        LogType.ai,
        '🤖 AI: "$cmd" → "$interpreted"',
      );
    }

    // ── Result log ────────────────────────────────────────────────
    final bool isError =
        result.toLowerCase().contains('not recognized') ||
        result.toLowerCase().contains('error') ||
        result.toLowerCase().startsWith('error:') ||
        result.contains('❌');     // ✅ catches emoji error markers too

    _addLog(isError ? LogType.error : LogType.success, result);

    // ── YouTube options list ──────────────────────────────────────
    if (options.isNotEmpty) {
      for (int i = 0; i < options.length; i++) {
        _addLog(LogType.sys, '  ${i + 1}. ${options[i]}');
      }
      _addLog(LogType.sys, "👉 Say 'play 1', 'play 2'... to play");
    }

    setState(() => _isProcessing = false);
    _focusNode.requestFocus();
  }

  // ────────────────────────────────────────────────────────────────
  // BUILD
  // ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildTopBar(),
            Expanded(
              child: TerminalLog(
                logs: _logs,
                scrollController: _scrollCtrl,
              ),
            ),
            QuickCommands(onCommand: _sendCommand),
            CommandInput(
              controller: _inputCtrl,
              focusNode: _focusNode,
              isProcessing: _isProcessing,
              isConnected: _isConnected,
              isListening: _isListening,
              onSend: () => _sendCommand(_inputCtrl.text),
              onMicTap: _toggleMic,
            ),
          ],
        ),
      ),
    );
  }

  // ── Top bar ─────────────────────────────────────────────────────

  Widget _buildTopBar() {
    return AnimatedBuilder(
      animation: _glowAnim,
      builder: (_, __) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: AppColors.surface,
          border: const Border(bottom: BorderSide(color: AppColors.border)),
          boxShadow: [
            BoxShadow(
              color: AppColors.accentBlue
                  .withValues(alpha: 0.06 * _glowAnim.value),
              blurRadius: 12,
            ),
          ],
        ),
        child: Row(
          children: [
            // ── Brand ───────────────────────────────────────────
            _glowingDot(
              _isConnected ? AppColors.successGreen : AppColors.errorRed,
            ),
            const SizedBox(width: 10),
            const Text(
              '⚡ FlowForge AI',
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 14,
                color: AppColors.accentBlue,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.2,
              ),
            ),
            const Spacer(),
            // ── Connection status ───────────────────────────────
            _statusPill(
              _isConnected ? '🟢 Connected' : '🔴 Disconnected',
              _isConnected ? AppColors.successGreen : AppColors.errorRed,
            ),
            const SizedBox(width: 10),
            // ── Workflows button ────────────────────────────────
            // ✅ From Aditya — navigates to WorkflowScreen
            IconButton(
              icon: const Icon(Icons.account_tree_outlined),
              color: AppColors.accentBlue,
              tooltip: 'Workflows',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const WorkflowScreen(),
                ),
              ),
            ),
            const SizedBox(width: 10),
            // ── Clock ───────────────────────────────────────────
            Text(
              _clockStr,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: AppColors.textSecondary.withValues(alpha: 0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _glowingDot(Color color) {
    return AnimatedBuilder(
      animation: _glowAnim,
      builder: (_, __) => Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color,
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.6 * _glowAnim.value),
              blurRadius: 8,
              spreadRadius: 1,
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusPill(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(4),
        color: color.withValues(alpha: 0.1),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontFamily: 'monospace',
          fontSize: 10.5,
          color: color,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}