#!/bin/bash

# 获取当前项目根目录
ROOT_DIR=$(git rev-parse --show-toplevel)

# 切换到项目根目录
cd "$ROOT_DIR" || exit 1

echo "Running lint-fix before commit..."

# 执行 make lint-fix 命令
make lint-fix

# 检查命令执行结果
if [ $? -ne 0 ]; then
    echo "Error: make lint-fix failed. Please fix the linting errors before committing."
    echo "You can run 'make lint-fix' manually to see and fix the errors."
    exit 1
fi

echo "Linting passed. Proceeding with commit..."
exit 0
