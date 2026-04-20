// lib/screens/workflow_screen.dart
// ──────────────────────────────────────────────────────────────────
// Full CRUD screen for Multi-Step Workflow Chains.
// Uses only ApiService — no changes to existing screens/widgets.
// ──────────────────────────────────────────────────────────────────

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../models/log_entry.dart'; // for AppColors

// ─────────────────────────────────────────
// API helpers (workflow-specific)
// ─────────────────────────────────────────

const String _base = 'http://127.0.0.1:8000';

Future<List<Map<String, dynamic>>> _fetchWorkflows() async {
  final res = await http.get(Uri.parse('$_base/workflows'));
  if (res.statusCode == 200) {
    final data = jsonDecode(res.body);
    return List<Map<String, dynamic>>.from(data['workflows']);
  }
  return [];
}

Future<String> _saveWorkflow(
    String name, String trigger, List<String> actions) async {
  final res = await http.post(
    Uri.parse('$_base/workflows'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'name': name, 'trigger': trigger, 'actions': actions}),
  );
  final data = jsonDecode(res.body);
  return data['message'] ?? 'Saved';
}

Future<String> _deleteWorkflow(String name) async {
  final res = await http.delete(
    Uri.parse('$_base/workflows'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'name': name}),
  );
  final data = jsonDecode(res.body);
  return data['message'] ?? 'Deleted';
}

// ─────────────────────────────────────────
// Screen
// ─────────────────────────────────────────

class WorkflowScreen extends StatefulWidget {
  const WorkflowScreen({super.key});

  @override
  State<WorkflowScreen> createState() => _WorkflowScreenState();
}

class _WorkflowScreenState extends State<WorkflowScreen> {
  List<Map<String, dynamic>> _workflows = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final list = await _fetchWorkflows();
    setState(() {
      _workflows = list;
      _loading = false;
    });
  }

  void _openCreateSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) => _CreateWorkflowSheet(
        onSaved: (name, trigger, actions) async {
          final msg = await _saveWorkflow(name, trigger, actions);
          if (mounted) {
            ScaffoldMessenger.of(context)
                .showSnackBar(SnackBar(content: Text(msg)));
            _load();
          }
        },
      ),
    );
  }

  Future<void> _delete(String name) async {
    final msg = await _deleteWorkflow(name);
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        title: const Text(
          '⚡ Workflow Chains',
          style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
        ),
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        elevation: 0,
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(color: AppColors.border, height: 1),
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _openCreateSheet,
        backgroundColor: AppColors.accentBlue,
        child: const Icon(Icons.add, color: Colors.black),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.accentBlue))
          : _workflows.isEmpty
              ? _EmptyState(onTap: _openCreateSheet)
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: _workflows.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (_, i) => _WorkflowCard(
                    workflow: _workflows[i],
                    onDelete: () => _delete(_workflows[i]['name']),
                  ),
                ),
    );
  }
}

// ─────────────────────────────────────────
// Workflow card
// ─────────────────────────────────────────

class _WorkflowCard extends StatelessWidget {
  final Map<String, dynamic> workflow;
  final VoidCallback onDelete;

  const _WorkflowCard({required this.workflow, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final actions = List<String>.from(workflow['actions'] ?? []);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(
            children: [
              Expanded(
                child: Text(
                  workflow['name'] ?? '',
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline,
                    color: Colors.redAccent, size: 18),
                onPressed: onDelete,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
            ],
          ),

          const SizedBox(height: 8),

          // Trigger
          Row(
            children: [
              const Icon(Icons.bolt, color: AppColors.accentBlue, size: 14),
              const SizedBox(width: 4),
              Text(
                'Trigger: ',
                style: TextStyle(
                    color: AppColors.textSecondary, fontSize: 12),
              ),
              Expanded(
                child: Text(
                  '"${workflow['trigger']}"',
                  style: const TextStyle(
                      color: AppColors.accentBlue,
                      fontSize: 12,
                      fontStyle: FontStyle.italic),
                ),
              ),
            ],
          ),

          const SizedBox(height: 6),
          const Divider(color: AppColors.border, height: 1),
          const SizedBox(height: 6),

          // Actions list
          ...actions.asMap().entries.map((e) => Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Text(
                      '${e.key + 1}.',
                      style: TextStyle(
                          color: AppColors.textSecondary, fontSize: 12),
                    ),
                    const SizedBox(width: 6),
                    const Icon(Icons.arrow_forward,
                        color: AppColors.textSecondary, size: 12),
                    const SizedBox(width: 4),
                    Text(
                      e.value,
                      style: const TextStyle(
                          color: AppColors.textPrimary, fontSize: 12),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────
// Create workflow bottom sheet
// ─────────────────────────────────────────

class _CreateWorkflowSheet extends StatefulWidget {
  final Future<void> Function(String, String, List<String>) onSaved;

  const _CreateWorkflowSheet({required this.onSaved});

  @override
  State<_CreateWorkflowSheet> createState() => _CreateWorkflowSheetState();
}

class _CreateWorkflowSheetState extends State<_CreateWorkflowSheet> {
  final _nameCtrl = TextEditingController();
  final _triggerCtrl = TextEditingController();
  final List<TextEditingController> _actionCtrls = [TextEditingController()];
  bool _saving = false;

  void _addAction() {
    setState(() => _actionCtrls.add(TextEditingController()));
  }

  void _removeAction(int i) {
    if (_actionCtrls.length == 1) return;
    setState(() {
      _actionCtrls[i].dispose();
      _actionCtrls.removeAt(i);
    });
  }

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    final trigger = _triggerCtrl.text.trim();
    final actions =
        _actionCtrls.map((c) => c.text.trim()).where((s) => s.isNotEmpty).toList();

    if (name.isEmpty || trigger.isEmpty || actions.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Fill in name, trigger and at least one action')));
      return;
    }

    setState(() => _saving = true);
    await widget.onSaved(name, trigger, actions);
    if (mounted) Navigator.pop(context);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _triggerCtrl.dispose();
    for (final c in _actionCtrls) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pad = MediaQuery.of(context).viewInsets.bottom + 24;

    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, pad),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'New Workflow Chain',
              style: TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.bold,
                  fontSize: 16),
            ),
            const SizedBox(height: 16),

            // Name
            _Field(ctrl: _nameCtrl, label: 'Workflow Name', hint: 'e.g. Morning Setup'),
            const SizedBox(height: 12),

            // Trigger
            _Field(
              ctrl: _triggerCtrl,
              label: 'Trigger Command',
              hint: 'e.g. open vscode',
              prefixIcon: Icons.bolt,
            ),
            const SizedBox(height: 16),

            const Text(
              'Chained Actions (run in order after trigger)',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
            const SizedBox(height: 8),

            // Actions
            ..._actionCtrls.asMap().entries.map((e) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    children: [
                      Text(
                        '${e.key + 1}.',
                        style: const TextStyle(
                            color: AppColors.textSecondary, fontSize: 13),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: _Field(
                          ctrl: e.value,
                          label: '',
                          hint: 'e.g. open chrome',
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.remove_circle_outline,
                            color: Colors.redAccent, size: 18),
                        onPressed: () => _removeAction(e.key),
                      ),
                    ],
                  ),
                )),

            // Add action button
            TextButton.icon(
              onPressed: _addAction,
              icon: const Icon(Icons.add, color: AppColors.accentBlue, size: 16),
              label: const Text('Add Action',
                  style: TextStyle(color: AppColors.accentBlue, fontSize: 13)),
            ),

            const SizedBox(height: 16),

            // Save button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.accentBlue,
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: _saving ? null : _submit,
                child: _saving
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.black))
                    : const Text('Save Workflow',
                        style: TextStyle(fontWeight: FontWeight.bold)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// Reusable text field
// ─────────────────────────────────────────

class _Field extends StatelessWidget {
  final TextEditingController ctrl;
  final String label;
  final String hint;
  final IconData? prefixIcon;

  const _Field(
      {required this.ctrl,
      required this.label,
      required this.hint,
      this.prefixIcon});

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: ctrl,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
      decoration: InputDecoration(
        labelText: label.isNotEmpty ? label : null,
        labelStyle:
            const TextStyle(color: AppColors.textSecondary, fontSize: 12),
        hintText: hint,
        hintStyle:
            const TextStyle(color: AppColors.textSecondary, fontSize: 12),
        prefixIcon: prefixIcon != null
            ? Icon(prefixIcon, color: AppColors.accentBlue, size: 16)
            : null,
        filled: true,
        fillColor: AppColors.background,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: AppColors.accentBlue),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// Empty state widget
// ─────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  final VoidCallback onTap;
  const _EmptyState({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.account_tree_outlined,
              color: AppColors.textSecondary, size: 48),
          const SizedBox(height: 12),
          const Text('No workflows yet',
              style:
                  TextStyle(color: AppColors.textPrimary, fontSize: 15)),
          const SizedBox(height: 4),
          const Text('Tap + to create your first chain',
              style: TextStyle(
                  color: AppColors.textSecondary, fontSize: 12)),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: onTap,
            icon: const Icon(Icons.add),
            label: const Text('Create Workflow'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.accentBlue,
              foregroundColor: Colors.black,
            ),
          ),
        ],
      ),
    );
  }
}