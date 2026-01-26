package controllers

// auth 身份认证 -包含各种对应路由的操作函数
import (
	"PgoAgent/global"
	"PgoAgent/models"
	"PgoAgent/utils"
	"errors"
	"net/http"
	"time"

	"PgoAgent/config"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

var (
	LoginTokenBucket    = utils.InitTokenBucket(1000, 100.0)
	RegisterTokenBucket = utils.InitTokenBucket(1000, 100.0)
)

// DTO数据
type RegisterDTO struct {
	Username string `json:"username" binding:"required,alphanum,min=3,max=32"`
	Password string `json:"password" binding:"required,min=6,max=64"`
}

type LoginDTO struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

// 缓存信息
type LoginInfo struct {
	ID       string
	Password string
	Username string
	Role     string
}

// Register godoc
// @Summary     用户注册
// @Tags        Auth
// @Accept      json
// @Produce     json
// @Param       body  body      controllers.RegisterDTO  true  "注册参数"
// @Success     200   {object}  map[string]string
// @Failure     400   {object}  map[string]string
// @Router      /auth/register [post]
func Register(c *gin.Context) {
	if !RegisterTokenBucket.TakeToken() { // 令牌桶控制
		c.JSON(http.StatusTooManyRequests, gin.H{"error": "Too many requests"})
		return
	}
	var in RegisterDTO //注册的DTO
	if err := c.ShouldBindJSON(&in); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	uname := in.Username

	hash, err := utils.HashPassword(in.Password) // 对其加密
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "hash password failed"})
		return
	}

	u := models.Users{ID: uuid.New().String(), Username: uname, Password: hash} //赋值,默认注册的用户都是普通用户

	if err := global.DB.Create(&u).Error; err != nil { //创建对应用户
		if errors.Is(err, gorm.ErrDuplicatedKey) {
			c.JSON(http.StatusConflict, gin.H{"error": "username has already existed"})
			return
		}
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	// 注册成功，先构建缓存
	global.UserCache.Set(uname, &LoginInfo{
		ID:       u.ID,
		Username: uname,
		Password: hash,
		Role:     u.Role, //数据库默认的缓存
	})
	token, err := utils.GenerateJWT(u.ID, u.Username, u.Role, config.WEBTOKEN)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "generate token failed"})
		return
	}
	utils.SetAuthCookie(c, token, utils.ExpireHours*time.Hour) //给上下文签发token和过i时间
	c.JSON(http.StatusCreated, gin.H{"token": token})          //正确码和对应的token后续就是直接跳转了
}

func CheckPassword(hash string, pwd string) bool {
	err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(pwd)) //第一个是hash加密过的密码，第二个是原装的密码-并不是字符串的比较
	return err == nil
}

// Login godoc
// @Summary     用户登录
// @Tags        Auth
// @Accept      json
// @Produce     json
// @Param       body  body      controllers.LoginDTO  true  "登录参数"
// @Success     200   {object}  map[string]string  "token"
// @Failure     400   {object}  map[string]string
// @Router      /auth/login [post]   // 注意：不要写 /api，已由 @BasePath /api 补齐
func Login(c *gin.Context) {
	if !LoginTokenBucket.TakeToken() { // 令牌桶控制
		c.JSON(http.StatusTooManyRequests, gin.H{"error": "Too many requests"})
		return
	}
	var in LoginDTO
	if err := c.ShouldBindJSON(&in); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	uname := in.Username
	if in.Username == "" || in.Password == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username and password are required"})
		return
	}

	var user LoginInfo
	userFromCache, exist := global.UserCache.Get(uname)
	if exist {
		if userFromCache, ok := userFromCache.(*LoginInfo); ok {
			user = *userFromCache // 直接等于指针
		} else {
			//后端调试信息
			c.JSON(http.StatusInternalServerError, gin.H{"error": "cache data error"})
			return
		}
	} else {
		var dbUser models.Users
		if err := global.DB.Where("username = ?", uname).First(&dbUser).Error; err != nil {
			// 不区分"用户不存在/密码错误"，统一提示，避免枚举用户名
			c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid username or password"})
			return
		}
		// 将 models.Users 转换为 LoginInfo
		user = LoginInfo{
			ID:       dbUser.ID,
			Username: dbUser.Username,
			Password: dbUser.Password,
			Role:     dbUser.Role,
		}
	}
	if !CheckPassword(user.Password, in.Password) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid username or password"})
		return
	}
	// 登录成功确保有效-更新缓存
	if exist == false {
		global.UserCache.Set(uname, &LoginInfo{
			ID:       user.ID,
			Username: uname,
			Password: user.Password,
			Role:     user.Role, //数据库默认的缓存
		})
	}
	token, err := utils.GenerateJWT(user.ID, user.Username, user.Role, config.WEBTOKEN)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "generate token failed"})
		return
	}
	utils.SetAuthCookie(c, token, utils.ExpireHours*time.Hour) //设定cookie
	c.JSON(http.StatusOK, gin.H{                               //正确码和对应的token
		"token": token,
	})
}

// Logout godoc
// @Summary     退出登录
// @Tags        Auth
// @Security    Bearer
// @Produce     json
// @Success     200   {object}  map[string]string
// @Router      /auth/logout [post]
// controllers/auth.go
func Logout(c *gin.Context) {
	utils.ClearAuthCookie(c) //清理cookie
	c.JSON(200, gin.H{"ok": true})
}

type deleteInput struct {
	Username string `json:"username"`
	Password string `json:"password"`
}


