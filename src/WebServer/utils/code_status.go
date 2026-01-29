package utils

import (
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// 文件统计
const (
	save_file = ".code_statistics"
	length    = 5 //代码历史list长度
)

type FileStats struct {
	Files int
	Lines int
	Size  int64
}

type CodeCounter struct {
	FileTypes      map[string][]string
	IgnoreDirs     map[string]bool
	ignorePatterns []string // 单独忽略的文件或通配符
	Results        map[string]FileStats
	ExtToLang      map[string]string // 文件名+后缀
	lastDir        string            // 上一次分析的目录
	history_record *ListQueue
	totalFiles     int
	totalLines     int
}

func NewCodeCounter() *CodeCounter {
	cc := &CodeCounter{
		FileTypes: map[string][]string{
			"Go":         {".go", ".mod", ".sum"},
			"Python":     {".py", ".pyw", ".pyi"},
			"JavaScript": {".js", ".jsx", ".ts", ".tsx", ".vue"},
			"Java":       {".java"},
			"C/C++":      {".c", ".cpp", ".cc", ".h", ".hpp"},
			"HTML":       {".html", ".htm"},
			"CSS":        {".css", ".scss", ".sass", ".less"},
			"PHP":        {".php"},
			"Ruby":       {".rb"},
			"Rust":       {".rs"},
			"Shell":      {".sh", ".bash", ".zsh", ".bat"},
			"Markdown":   {".md", ".markdown"},
			"YAML":       {".yml", ".yaml"},
			"TOML":       {".toml"},
			// "JSON":       {".json"},  //忽略，多为微调的数据集模板
			"XML":    {".xml"},
			"SQL":    {".sql"},
			"txt":    {".txt"},
			"Docker": {".dockerfile", ".dockerignore"},
		},
		// 易错
		IgnoreDirs: map[string]bool{ // 忽略的目录-这里是提前写死了
			".venv":        true,
			"chromadb":     true,
			".git":         true,
			"node_modules": true,
			"vendor":       true,
			"dist":         true,
			"build":        true,
			"__pycache__":  true,
			".idea":        true,
			".vscode":      true,
			"target":       true, // Java/Scala
			"bin":          true, // 常见构建输出
			"obj":          true, // .NET
			"coverage":     true,
		},
		Results:        make(map[string]FileStats),
		ExtToLang:      make(map[string]string),
		history_record: NewListQueue(), // 初始化历史记录队列
	}
	// 构建反向索引：文件名 -> 语言(后缀名)
	for lang, files := range cc.FileTypes { // 遍历语言文件-lang是键，exts是值
		// 内部遍历文件名
		for _, file := range files {
			cc.ExtToLang[strings.ToLower(file)] = lang //转换为小名
		}
	}

	// 尝试加载当前的历史记录
	cc.loadHistory()
	return cc
}

func (cc *CodeCounter) Analyze(dir string, gitignore *GitIgnore) error { // 分析当前路径
	cc.lastDir = dir // 设置为当前路径
	cc.totalFiles = 0
	cc.totalLines = 0
	defer cc.save(dir)                                                               // 最后保存文件
	return filepath.WalkDir(dir, func(path string, d fs.DirEntry, err error) error { // 实现这一接口-递归走法2
		if err != nil {
			// 权限等问题直接跳过该节点
			return nil
		}
		// gitignore匹配
		if gitignore != nil { //如果文件不存在就不考虑
			ignored, matchErr := gitignore.MatchGitIgnore(path, d.IsDir())
			if matchErr != nil {
				return fmt.Errorf("failed to match gitignore for %s: %w", path, matchErr)
			}
			if ignored { // 如果给出忽略标志
				if d.IsDir() {
					return fs.SkipDir
				}
				return nil
			}
		}
		name := d.Name() // 文件名

		if d.IsDir() { // 跳过先前自定义的忽略目录
			if cc.IgnoreDirs[name] {
				return fs.SkipDir // 直接跳过文件夹
			}
			return nil
		}
		// 跳过自定义的忽略文件或通配符
		if cc.shouldIgnoreFile(path, name) { // 判断是否是我们需要忽略的文件
			return nil
		}

		ext := strings.ToLower(filepath.Ext(name)) //只会返回单一文件的后缀名即拓展名
		lang, ok := cc.ExtToLang[ext]
		if !ok {
			return nil
		}

		lines, size, err := cc.countLinesFast(path)
		if err != nil {
			// 大文件/异常读失败时跳过该文件
			return nil
		}
		stats := cc.Results[lang]
		stats.Files++
		stats.Lines += lines
		stats.Size += size
		cc.Results[lang] = stats
		cc.totalFiles++
		cc.totalLines++
		return nil
	})
}

func (cc *CodeCounter) save(dir string) {
	now := time.Now()
	timeStr := now.Format("2006-01-02 15:04:05")
	record := map[string]string{
		"filepath": dir, // 修正拼写错误
		"count":    fmt.Sprintf("%d", cc.totalFiles),
		"time":     timeStr,
	}
	cc.history_record.Enqueue(record) //进队
	if cc.history_record.Size() > length {
		cc.history_record.Dequeue()
	}

	// 保存历史记录到文件
	cc.saveHistoryToFile()
}

// saveHistoryToFile 将历史记录保存到文件
func (cc *CodeCounter) saveHistoryToFile() {
	// 获取所有历史记录
	records := cc.history_record.GetAll() //获取队列的数据

	// 将记录转换为JSON格式
	data, err := json.Marshal(records)
	if err != nil {
		fmt.Printf("序列化历史记录失败: %v\n", err)
		return
	}

	// 创建历史记录文件路径（使用当前工作目录）
	configDir := save_file
	if err := os.MkdirAll(configDir, 0755); err != nil {
		fmt.Printf("创建配置目录失败: %v\n", err)
		return
	}

	filePath := filepath.Join(configDir, "history.json")

	// 写入文件以替代-如果是修改则是打开后写会，我们这里是覆盖直接写入
	if err := os.WriteFile(filePath, data, 0644); err != nil {
		fmt.Printf("保存历史记录失败: %v\n", err)
		return
	}
}

// loadHistory 从文件加载历史记录
func (cc *CodeCounter) loadHistory() {
	// 创建历史记录文件路径（使用当前工作目录）
	configDir := save_file
	filePath := filepath.Join(configDir, "history.json")

	// 检查文件是否存在
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		// 文件不存在，无需加载
		return
	}

	// 读取文件内容
	data, err := os.ReadFile(filePath)
	if err != nil {
		fmt.Printf("读取历史记录失败: %v\n", err)
		return
	}

	// 解析JSON数据-这个是键值对切片数据
	var records []map[string]string
	if err := json.Unmarshal(data, &records); err != nil {
		fmt.Printf("解析历史记录失败: %v\n", err)
		return
	}

	// 将记录添加到队列中-很关键
	for _, record := range records {
		cc.history_record.Enqueue(record)
	}
}

// countLinesFast：块读取 + 计 '\n'，避免 bufio.Scanner 的 64K 单行限制
func (cc *CodeCounter) countLinesFast(filename string) (int, int64, error) {
	f, err := os.Open(filename)
	if err != nil {
		return 0, 0, err
	}
	defer f.Close()

	buf := make([]byte, 64*1024) // 64KB 块
	var (
		lines    int
		size     int64
		lastByte byte = '\n' // 若文件为空，不会 +1；非空且最后不是 '\n'，最后补一行
	)
	for {
		n, e := f.Read(buf)
		if n > 0 {
			size += int64(n) //读取的字节数量
			b := buf[:n]
			lastByte = b[n-1]
			// 计换行
			for i := 0; i < n; i++ {
				if b[i] == '\n' {
					lines++
				}
			}
		}
		if e == io.EOF {
			break
		}
		if e != nil {
			return lines, size, e
		}
	}
	// 末尾无 '\n' 也算一行（常见于最后一行）
	if size > 0 && lastByte != '\n' {
		lines++
	}
	return lines, size, nil
}

func (cc *CodeCounter) PrintReport() {
	totalFiles := 0
	totalLines := 0
	var totalSize int64 = 0

	for _, stats := range cc.Results {
		totalFiles += stats.Files
		totalLines += stats.Lines
		totalSize += stats.Size
	}

	type LangStats struct {
		Lang  string
		Stats FileStats
	}
	var sorted []LangStats
	for lang, stats := range cc.Results {
		if stats.Files > 0 {
			sorted = append(sorted, LangStats{Lang: lang, Stats: stats})
		}
	}

	// 按行数排序
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Stats.Lines > sorted[j].Stats.Lines
	})
	fmt.Printf("📊 本项目PgoAgent详细代码统计报告\n")
	fmt.Println(strings.Repeat("=", 75))
	fmt.Printf("%-11s %8s %12s %12s %8s\n", "文件类型", "文件数", "代码行数", "文件大小", "占比")
	fmt.Println(strings.Repeat("-", 75))

	for _, item := range sorted {
		percentage := 0.0
		if totalLines > 0 {
			percentage = float64(item.Stats.Lines) / float64(totalLines) * 100
		}
		size, uint := chooseSize(item.Stats.Size) //统计它的大小来以为单位
		fmt.Printf("%-15s %8d     %12d     %12.2f"+uint+"    %7.1f%%\n",
			item.Lang, item.Stats.Files, item.Stats.Lines, size, percentage)
	}

	fmt.Println(strings.Repeat("=", 75))
	total, totalUint := chooseSize(totalSize)

	fmt.Printf("%s: %d个文件数| %d行数 |%.2f"+totalUint+"\n",
		"总计", totalFiles, totalLines, total)

	// 文件数量 Top5
	fmt.Printf("\n🏆 文件数量排名:\n")
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Stats.Files > sorted[j].Stats.Files
	})
	for i := 0; i < len(sorted) && i < 5; i++ {
		fmt.Printf("  %2d. %-12s: %d 个文件\n", i+1, sorted[i].Lang, sorted[i].Stats.Files)
	}
	fmt.Println(strings.Repeat("=", 75))
	fmt.Println("历史记录:")
	for index, node := range cc.history_record.GetAll() {
		if r, ok := node.(map[string]string); ok {
			fmt.Printf("索引:%d 路径: %s 文件数: %4s 记录时间: %s\n",
				index+1, r["filepath"], r["count"], r["time"])
		}
	}
	fmt.Println(strings.Repeat("=", 75))
}
func chooseSize(size int64) (float64, string) {
	const (
		KB = 1024
		MB = KB * 1024
		GB = MB * 1024
	)
	switch {
	case size < KB:
		return float64(size), "B " //保证统一
	case size < MB:
		return float64(size) / KB, "KB"
	case size < GB:
		return float64(size) / MB, "MB"
	default:
		return float64(size) / GB, "GB"
	}
}

// IgnoreFiles 允许外部注入需要忽略的文件或通配符（如 *.log、docs/*.md）
func (cc *CodeCounter) IgnoreFiles(patterns ...string) *CodeCounter {
	for _, p := range patterns { // 遍历可变参数
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		cc.ignorePatterns = append(cc.ignorePatterns, filepath.ToSlash(p))
	}
	return cc
}

// 这里是自定义的文件进行忽略
func (cc *CodeCounter) shouldIgnoreFile(path, name string) bool {
	if len(cc.ignorePatterns) == 0 { // 如果忽略的文件或通配符为空，则不忽略
		return false
	}
	normalized := filepath.ToSlash(path)
	for _, pattern := range cc.ignorePatterns {
		target := name
		if strings.Contains(pattern, "/") { // 包含/则用标准化的完整路径来替代使用
			target = normalized
		}
		if ok, err := filepath.Match(pattern, target); err == nil && ok {
			return true
		}
		if target == pattern {
			return true
		}
	}
	return false
}
