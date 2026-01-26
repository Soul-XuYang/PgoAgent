package router
import (
	"fmt"
	"PgoAgent/config"
	"PgoAgent/global"
	"PgoAgent/models"
	"PgoAgent/utils"

)
const (
	defaultUserName     = "admin"
	defaultUserPassword = "123456"
)	

func initDefaultUser() error {
	// 使用Count代替First，避免record not found日志
	var count int64
	// 这里按用户名检查是否已存在默认用户，避免对 UUID 主键使用固定字符串导致 PostgreSQL 报错
	err := global.DB.Model(&models.Users{}).Where("username = ?", defaultUserName).Count(&count).Error
	if err != nil {
		return fmt.Errorf("failed to check user existence: %v", err)
	}
	if count > 0 {
		return nil
	}

	hash, err := utils.HashPassword(defaultUserPassword) 	// 这个易错，易遗忘
	if err != nil {
		return fmt.Errorf("failed to hash default user password: %v", err)
	}

	// 创建默认用户（不手动设置 ID，让 PostgreSQL 自动生成 UUID）
	defaultUser := models.Users{
		Username: defaultUserName,
		Password: hash,
		Role:     "admin",
	}

	if err := global.DB.Create(&defaultUser).Error; err != nil {
		return fmt.Errorf("failed to create default user: %v", err)
	}

	return nil
}
// Run 启动Web服务器 
// - mode: DEBUG or RELEASE
func Run(mode string){
	if mode == "DEBUG" {
		initDefaultUser()
	} 
	r:= SetupRouter()
	fmt.Println("4. Router has initilized")
	webServerAddr :=  fmt.Sprintf("%s:%d", config.ConfigHandler.WEBSERVER.Config.Host, config.ConfigHandler.WEBSERVER.Config.Port)
	fmt.Printf("5. PgoAgent Web server is running at http://%s\n", webServerAddr)
	r.Run(webServerAddr) // listen and serve on
}

