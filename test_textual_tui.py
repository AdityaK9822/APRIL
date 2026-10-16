#!/usr/bin/env python3
"""Test script for APRIL Textual TUI"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from core.textual_tui import APRILApp, get_agent, main
        print("✓ core.textual_tui imports successfully")
    except Exception as e:
        print(f"✗ core.textual_tui import failed: {e}")
        return False
    
    try:
        from core.widgets import StatusWidget, MessageList, InputWidget, LogPanel, StatsWidget
        print("✓ core.widgets imports successfully")
    except Exception as e:
        print(f"✗ core.widgets import failed: {e}")
        return False
    
    try:
        from textual.app import App
        print("✓ textual imports successfully")
    except Exception as e:
        print(f"✗ textual import failed: {e}")
        return False
    
    return True

def test_widgets():
    """Test widget instantiation"""
    print("\nTesting widgets...")
    
    from core.widgets import StatusWidget, MessageList, InputWidget, LogPanel, StatsWidget
    
    # StatusWidget
    try:
        widget = StatusWidget()
        print("✓ StatusWidget instantiated")
    except Exception as e:
        print(f"✗ StatusWidget failed: {e}")
        return False
    
    # MessageList
    try:
        widget = MessageList()
        print("✓ MessageList instantiated")
    except Exception as e:
        print(f"✗ MessageList failed: {e}")
        return False
    
    # InputWidget
    try:
        widget = InputWidget()
        print("✓ InputWidget instantiated")
    except Exception as e:
        print(f"✗ InputWidget failed: {e}")
        return False
    
    # LogPanel
    try:
        widget = LogPanel()
        print("✓ LogPanel instantiated")
    except Exception as e:
        print(f"✗ LogPanel failed: {e}")
        return False
    
    return True

def test_app():
    """Test app instantiation"""
    print("\nTesting app...")
    
    from core.textual_tui import APRILApp
    
    try:
        app = APRILApp()
        print("✓ APRILApp instantiated")
        print(f"  - CSS_PATH: {app.CSS_PATH}")
        print(f"  - BINDINGS: {len(app.BINDINGS)} shortcuts")
    except Exception as e:
        print(f"✗ APRILApp failed: {e}")
        return False
    
    return True

def main():
    print("=" * 60)
    print("APRIL Textual TUI - Test Suite")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Widgets", test_widgets()))
    results.append(("App", test_app()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\nAll tests passed! ✓")
        print("\nTo run the actual TUI:")
        print("  python3 -m core.textual_tui")
        print("  python3 -m core.textual_tui --agent  # with agent")
    else:
        print("\nSome tests failed! ✗")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
