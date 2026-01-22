package utils

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type GitIgnore struct {
	patterns []string
	root     string // .gitignore 文件所在的根目录
}

// NewGitIgnore 创建一个新的 GitIgnore 对象实例-指针类型
func NewGitIgnore(gitignorePath string) (*GitIgnore, error) { // 这里打开对应的.gitignore文件，并逐行读取不读注释
	file, err := os.Open(gitignorePath) // 获得文件对象指针
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil //如果文件不存在，则返回空
		}
		return nil, fmt.Errorf("failed to open .gitignore: %w", err)
	}
	defer file.Close()

	gi := &GitIgnore{
		root: filepath.Dir(gitignorePath),
	}

	scanner := bufio.NewScanner(file) // 它提供了一个简单的方式来逐行或按分隔符读取输入
	for scanner.Scan() {              // 逐步读取行内容
		line := strings.TrimSpace(scanner.Text()) // 转化为字符串
		// 跳过空行和注释
		if line == "" || strings.HasPrefix(line, "#") { //跳过空行和注释-这都被忽略
			continue
		}
		// 处理否定模式（以!开头）
		if strings.HasPrefix(line, "!") {
			line = "!" + strings.TrimSpace(line[1:])
		}

		gi.patterns = append(gi.patterns, line)
	}

	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("error reading .gitignore: %v", err)
	}
	gi.patterns = append(gi.patterns, ".gitignore") //忽略.gitignore文件本身
	return gi, nil
}

// MatchGitIgnore 检查文件路径是否匹配 gitignore 规则
func (gi *GitIgnore) MatchGitIgnore(path string, isDir bool) (bool, error) { // 这里针对于!和目录规则进行了处理
	if gi == nil { //如果gitignore为空，则返回false就是完全没有我们需要的忽略文件
		return false, nil
	}
	// 将路径转换为相对于 .gitignore 所在目录的相对路径
	relPath, err := filepath.Rel(gi.root, path) // 依据根目录获得相对路径
	if err != nil {
		return false, err
	}
	// 标准化即统一所有路径
	normalizedPath := strings.TrimPrefix(filepath.ToSlash(relPath), "./")
  

	var ignored bool
	for _, raw := range gi.patterns { 	// 遍历所有规则来判断是否匹配
		pattern := strings.TrimSpace(raw)
		if pattern == "" {
			continue
		}
		// 处理否定规则
		negate := strings.HasPrefix(pattern, "!") // 不忽略规则
		if negate {
			pattern = strings.TrimSpace(pattern[1:])
		}

		if pattern == "" {
			continue
		}
        // 看是否符合规则
		if gi.matchPattern(pattern, normalizedPath, isDir) { //这里根据是否文件来加以分别判断
			ignored = !negate //取反
		}
	}

	return ignored, nil
}

func (gi *GitIgnore) matchPattern(pattern, target string, isDir bool) bool { // 第一个为gitignore规则，第二个为文件路径
	pattern = filepath.ToSlash(pattern)
	target = strings.TrimPrefix(target, "./") //移除./

	rooted := strings.HasPrefix(pattern, "/")
	dirPattern := strings.HasSuffix(pattern, "/") 
	if rooted {
		pattern = strings.TrimPrefix(pattern, "/") //移除开头的/ 表示从它为根目录匹配计算
	}

	if dirPattern {
		pattern = strings.TrimSuffix(pattern, "/")
	}

	if pattern == "" { //完全为空
		return false
	}


	// 上述验证是否为否为目录规则和根目录规则

	matchCandidate := target //当前的匹配对象
	if !rooted && !strings.Contains(pattern, "/") { //这里是针对于没有路径的规则，只匹配文件名-文件名的通配符
		matchCandidate = filepath.Base(target) //只用文件名匹配
	}

	// 目录规则：匹配该目录以及目录下的所有文件
	if dirPattern { //如果是目录规则
		if target == pattern || strings.HasPrefix(target, pattern+"/") { //匹配目录或者前缀一样即路径一样
			return true
		}
		return false
	}

	if matched := globMatch(pattern, matchCandidate); matched { //标准匹配
		return true
	}

	// 未包含路径时，再尝试与完整路径匹配一次
	// if !strings.Contains(pattern, "/") && globMatch(pattern, target) {
	// 	return true
	// }

	// 目录尝试附加 / 以兼容部分写法
	if isDir && globMatch(pattern, target+"/") { //兼容temp这种按照temp/的目录规则
		return true
	}

	return false
}

func globMatch(pattern, candidate string) bool {
	if candidate == "" {
		candidate = "." //当前目录
	}
	ok, err := filepath.Match(pattern, candidate) //判断是否匹配
	if err != nil {
		return false
	}
	return ok
}

// 测试示例
func testIgnore() {
	// 创建 .gitignore 解析器
	gitignore, err := NewGitIgnore(".gitignore")
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		return
	}
	if gitignore == nil {
		fmt.Println(".gitignore not found")
		return
	}

	// 测试文件路径-实际上是我们遍历文件夹遇到的一些测试路径
	testFiles := []string{
		"vendor/package/file.go",
		"build/output.exe",
		"README.md",
		"src/main.go",
		"test/main_test.go",
		".env",
	}

	// 检查每个文件是否应该被忽略
	for _, file := range testFiles { //遍历路径
		ignored, err := gitignore.MatchGitIgnore(file, false)
		if err != nil {
			fmt.Printf("Error matching %s: %v\n", file, err)
			continue
		}
		fmt.Printf("%s: ignored=%v\n", file, ignored)
	}
}
