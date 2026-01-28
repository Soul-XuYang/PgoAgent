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

	// 用户信息相关（需要认证）
	profile := apiV1.Group("/profile", middlewares.JWTAuthMiddleware())
	{
		profile.GET("", controllers.GetInfo)
		profile.GET("/store", controllers.GetUserLongTermMemory)
		profile.POST("/store", controllers.SetUserLongTermMemory)
		profile.DELETE("/store",controllers.DeleteUserLongTermMemory)
	}

	// 对话相关路由（需要认证）
	conversations := apiV1.Group("/conversations", middlewares.JWTAuthMiddleware()) //认证中间件
	{
		// 列出当前用户的对话列表
		conversations.GET("", controllers.ListConversations)
		// 创建会话并写入首条消息
		conversations.POST("", controllers.CreateConversations)
		// 获取指定会话下的消息列表
		conversations.GET("/:id/messages", controllers.ListConversationMessages)
		// 继续在已有会话下发消息
		conversations.POST("/:id/messages", controllers.SendMessage)
		// 取消当前会话对应的大模型任务
		conversations.POST("/:id/cancel", controllers.CancelConversation)
		// 删除指定会话
		conversations.DELETE("/:id", controllers.DeleteConversation)
	}

	// 聊天页面路由（需要认证）
	r.GET("/chat", middlewares.JWTAuthMiddleware(), func(c *gin.Context) {
		c.HTML(200, "chat.html", nil)
	})

	return r
}
