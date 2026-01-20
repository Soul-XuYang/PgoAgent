package router

// 构建对应的网路路由
import (
	"PgoAgent/controllers"
	"PgoAgent/middlewares"

	"github.com/gin-gonic/gin"
)

func SetupRouter() *gin.Engine {
	r := gin.New() // 创建初始化路由器指针
	r.Use(middlewares.GinLogger(), middlewares.GinRecovery())

	//记载对应的html
	r.LoadHTMLGlob("static/*.html")
	r.Static("/static", "static")

	// 根路径路由
	r.GET("/", func(c *gin.Context) { c.HTML(200, "entry.html", nil) })

	apiV1 := r.Group("/api/v1")
	auth := apiV1.Group("/auth")
	{
		// 登录注册登出删除
		auth.POST("/login", controllers.Login)
		auth.POST("/register", controllers.Register)
		auth.POST("/logout", middlewares.JWTAuthMiddleware(), controllers.Logout)
		auth.DELETE("/delete", middlewares.JWTAuthMiddleware(), controllers.DeleteUser)
	}

	// 对话相关路由（需要认证）
	conversations := apiV1.Group("/conversations", middlewares.JWTAuthMiddleware())
	{
		conversations.GET("/create", controllers.CreateConversations)
		conversations.POST("/:id/messages", controllers.SendMessage)

	}

	// 聊天页面路由（需要认证）
	r.GET("/chat", middlewares.JWTAuthMiddleware(), func(c *gin.Context) {
		c.HTML(200, "chat.html", nil)
	})

	return r
}
