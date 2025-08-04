#!/usr/bin/env python3
"""Скрипт для запуска SCIM Proxy Service"""

import sys
import os
import subprocess
import argparse


def run_server():
    """Запуск сервера разработки"""
    print("🚀 Запуск SCIM Proxy Service...")
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n✋ Сервер остановлен")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска сервера: {e}")
        sys.exit(1)


def run_tests():
    """Запуск тестов"""
    print("🧪 Запуск тестов...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v", 
            "--tb=short"
        ], check=False)
        if result.returncode == 0:
            print("✅ Все тесты прошли успешно!")
        else:
            print("❌ Некоторые тесты не прошли")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска тестов: {e}")
        sys.exit(1)


def install_deps():
    """Установка зависимостей"""
    print("📦 Установка зависимостей...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "-r", "requirements-dev.txt"
        ], check=True)
        print("✅ Зависимости установлены успешно!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        sys.exit(1)


def lint_code():
    """Проверка кода линтерами"""
    print("🔍 Проверка кода...")
    
    # Black
    print("  Форматирование с Black...")
    try:
        subprocess.run([
            sys.executable, "-m", "black", 
            "app/", "tests/", "--check"
        ], check=True)
        print("  ✅ Black: код отформатирован правильно")
    except subprocess.CalledProcessError:
        print("  ⚠️  Black: требуется форматирование")
        subprocess.run([
            sys.executable, "-m", "black", 
            "app/", "tests/"
        ])
        print("  ✅ Black: код отформатирован")
    
    # Flake8
    print("  Проверка с Flake8...")
    try:
        subprocess.run([
            sys.executable, "-m", "flake8", 
            "app/", "tests/"
        ], check=True)
        print("  ✅ Flake8: проблем не найдено")
    except subprocess.CalledProcessError:
        print("  ❌ Flake8: найдены проблемы")


def docker_build():
    """Сборка Docker образа"""
    print("🐳 Сборка Docker образа...")
    try:
        subprocess.run([
            "docker", "build", "-t", "scim-proxy", "."
        ], check=True)
        print("✅ Docker образ собран успешно!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки Docker образа: {e}")
        sys.exit(1)


def docker_run():
    """Запуск в Docker"""
    print("🐳 Запуск в Docker...")
    try:
        subprocess.run([
            "docker-compose", "up", "--build"
        ], check=True)
    except KeyboardInterrupt:
        print("\n✋ Docker контейнер остановлен")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка запуска Docker: {e}")
        sys.exit(1)


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="SCIM Proxy Service управление")
    parser.add_argument(
        "command", 
        choices=["server", "test", "install", "lint", "docker-build", "docker-run"],
        help="Команда для выполнения"
    )
    
    args = parser.parse_args()
    
    if args.command == "server":
        run_server()
    elif args.command == "test":
        run_tests()
    elif args.command == "install":
        install_deps()
    elif args.command == "lint":
        lint_code()
    elif args.command == "docker-build":
        docker_build()
    elif args.command == "docker-run":
        docker_run()


if __name__ == "__main__":
    main()