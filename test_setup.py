#!/usr/bin/env python3
"""
Test script to validate the bot setup without running it
"""

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import os
        import aiogram
        from aiogram import Bot, Dispatcher, types, F
        from aiogram.filters import Command
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.state import State, StatesGroup
        from aiogram.fsm.storage.memory import MemoryStorage
        from aiogram.utils.keyboard import ReplyKeyboardBuilder
        from dotenv import load_dotenv
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_env_setup():
    """Test environment file setup"""
    import os
    if os.path.exists('.env'):
        print("✅ .env file exists")
        from dotenv import load_dotenv
        load_dotenv()
        token = os.getenv("BOT_TOKEN")
        if token:
            print("✅ BOT_TOKEN is set")
        else:
            print("⚠️  BOT_TOKEN is not set in .env file")
    else:
        print("⚠️  .env file not found. Copy .env.example to .env and add your bot token")

def test_bot_structure():
    """Test that bot file has correct structure"""
    try:
        with open('bot.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_elements = [
            'class DriverStates',
            'get_main_keyboard',
            'dp.message',
            'dp.run_polling'
        ]
        
        for element in required_elements:
            if element in content:
                print(f"✅ Found: {element}")
            else:
                print(f"❌ Missing: {element}")
        
        return True
    except Exception as e:
        print(f"❌ Error reading bot.py: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing Telegram Bot Setup...")
    print("\n1. Testing imports:")
    test_imports()
    
    print("\n2. Testing environment setup:")
    test_env_setup()
    
    print("\n3. Testing bot structure:")
    test_bot_structure()
    
    print("\n�� Setup validation complete!")
    print("\nTo run the bot:")
    print("1. Create .env file: cp .env.example .env")
    print("2. Add your bot token to .env file")
    print("3. Run: python bot.py")
