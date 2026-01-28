package config

import (
	"fmt"
	"os"
	"runtime"
	"strings"
	"time"
)

// ASCII艺术字（与Python版本完全一致）
var asciiArt = []string{
	"░█████████                           ░███                                        ░██    ",
	"░██     ░██                         ░██░██                                       ░██    ",
	"░██     ░██  ░████████  ░███████   ░██  ░██   ░████████  ░███████  ░████████  ░████████ ",
	"░█████████  ░██    ░██ ░██    ░██ ░█████████ ░██    ░██ ░██    ░██ ░██    ░██    ░██    ",
	"░██         ░██    ░██ ░██    ░██ ░██    ░██ ░██    ░██ ░█████████ ░██    ░██    ░██    ",
	"░██         ░██   ░███ ░██    ░██ ░██    ░██ ░██   ░███ ░██        ░██    ░██    ░██    ",
	"░██          ░█████░██  ░███████  ░██    ░██  ░█████░██  ░███████  ░██    ░██     ░████ ",
	"                   ░██                              ░██                                 ",
	"             ░███████                         ░███████                                  ",
	"                                                                                        ",
}

// 颜色和样式映射（对应Python的color_bar和font_type）
var (
	colorCodes = map[string]string{
		"black":   "30",
		"red":     "31",
		"green":   "32",
		"yellow":  "33",
		"blue":    "34",
		"magenta": "35",
		"cyan":    "36",
		"white":   "37",
	}

	fontStyles = map[string]string{
		"bold":      "1",
		"dark":      "2",
		"italic":    "3",
		"underline": "4",
		"blink":     "5",
		"reverse":   "7",
		"concealed": "8",
	}
)
const terminalWidth = 88 // 使用固定宽度
// coloredPrint 彩色打印函数（对应Python的colored_print）
func coloredPrint(text string, colorCode string, end string, center bool) {
	var displayText string
	// 居中处理
	if center {
		padding := (terminalWidth - len(text)) / 2 // 计算开头位置
		if padding > 0 {
			displayText = strings.Repeat(" ", padding) + text
		} else { //超出不居中
			displayText = text
		}
	} else {
		displayText = text
	}
	// 彩色打印（ANSI转义码）
	fmt.Printf("\033[%sm%s\033[0m%s", colorCode, displayText, end)
	os.Stdout.Sync() // 强制刷新输出
}


func AnimatedBanner() {
	// 打印空行
	fmt.Println(strings.Repeat("\n", 2))

	// 打字机效果逐行打印ASCII艺术字
	for _, line := range asciiArt {
		for _, char := range line {
			fmt.Print(string(char))
			os.Stdout.Sync()                 // 立即刷新输出缓冲区，确保字符立即显示
			time.Sleep(1 * time.Millisecond) // 对应0.001秒
		}
		fmt.Println()
		time.Sleep(50 * time.Millisecond) // 对应0.05秒
	}

	// 分隔线和信息
	fmt.Println("\n" + strings.Repeat("═", 88))
	// 粗体黄色
	boldYellow := fontStyles["bold"] + ";" + colorCodes["yellow"]
	// 获取Go版本
	goVersion := strings.TrimPrefix(runtime.Version(), "go")
	infoLine1 := fmt.Sprintf(" PgoAgent: %s | system: %s | go: %s ", VERSION, runtime.GOOS, goVersion)
	coloredPrint(infoLine1, boldYellow, "\n", true)
	// italic + cyan 字体
	italicCyan := fontStyles["italic"] + ";" + colorCodes["cyan"]
	startTime := time.Now().Format("2006-01-02 15:04:05") // Go的时间格式化模板
	infoLine2 := fmt.Sprintf("WebClient: start_time: %s", startTime)
	coloredPrint(infoLine2, italicCyan, "\n", true)

	fmt.Println(strings.Repeat("═", 88) + "\n")
}

func SimpleBanner() {
	// 快速打印ASCII艺术字
    fmt.Println()
	fmt.Println(strings.Join(asciiArt, "\n")) // go的字符串拼接-字符串
		// 分隔线和信息
	fmt.Println("\n" + strings.Repeat("═", 88))
	// 粗体黄色
	boldYellow := fontStyles["bold"] + ";" + colorCodes["yellow"]
	// 获取Go版本
	goVersion := strings.TrimPrefix(runtime.Version(), "go")
	infoLine1 := fmt.Sprintf(" PgoAgent: %s | system: %s | go: %s ", VERSION, runtime.GOOS, goVersion)
	coloredPrint(infoLine1, boldYellow, "\n", true)
	// italic + cyan 字体
	italicCyan := fontStyles["italic"] + ";" + colorCodes["cyan"]
	startTime := time.Now().Format("2006-01-02 15:04:05") // Go的时间格式化模板
	infoLine2 := fmt.Sprintf("WebClient: start_time: %s", startTime)
	coloredPrint(infoLine2, italicCyan, "\n", true)

	fmt.Println(strings.Repeat("═", 88) + "\n")
}


