package models

import (
	"time"
)

// 用户角色常量
const (
	RoleNormal     = "user"       // 普通用户
	RoleAdmin      = "admin"      // 管理员
	RoleSuperAdmin = "superadmin" // 超级管理员
)

// 客户端用户数据
type Users struct {
    ID        string   `gorm:"type:uuid;default:gen_random_uuid();primaryKey"`//uuid,支持postgresql
    CreatedAt time.Time
    UpdatedAt time.Time

    Username     string `gorm:"size:64;uniqueIndex;not null"`
    Password     string `gorm:"size:255;not null"` // 存的是加密密码

    Role string `gorm:"type:varchar(16);not null;default:'user';check:role in ('user','admin','superadmin')"`

    Conversations []Conversations `gorm:"foreignKey:UserID;constraint:OnUpdate:CASCADE,OnDelete:CASCADE"`
}

// Conversations：会话（用户创建多个会话）
type Conversations struct {
    ID        string    `gorm:"type:uuid;default:gen_random_uuid();primaryKey;index"` //uuid,支持postgresql
    CreatedAt time.Time
    UpdatedAt time.Time

	UserID string `gorm:"type:uuid;not null;index"`
    User Users `gorm:"foreignKey:UserID;references:ID;constraint:OnUpdate:CASCADE,OnDelete:CASCADE"`
    
	ConversationName string `gorm:"size:64;not null"`
    // 这个用指针是为了判断是否为空
    LastMessageID *uint64    `gorm:"index;null"`
    LastMsgTime   *time.Time `gorm:"type:timestamp;null;index"`
    Messages []Messages `gorm:"foreignKey:ConversationID"`
}

// Messages：消息（属于某个会话）
type Messages struct {
    ConversationID string `gorm:"type:uuid;not null;index:idx_conv_id_id,priority:1"`
    ID             uint64 `gorm:"primaryKey;autoIncrement;not null;index:idx_conv_id_id,priority:2"`
    Conversation   Conversations `gorm:"foreignKey:ConversationID;references:ID;constraint:OnUpdate:CASCADE,OnDelete:CASCADE;"`
    
    CreatedAt time.Time
    // 单用户↔AI：不需要 UserID
    // role 至少预留 system/tool，后面扩展不用改表目前就是先用user和assistant
    Role    string `gorm:"type:varchar(16);not null;check:role in ('user','assistant','system','tool')"` //对postgresql约束
    Content string `gorm:"type:text;not null"`
}

// 显式标明表名
func (Users) TableName() string {
	return "users"
}

func (Conversations) TableName() string {
	return "conversations"
}

func (Messages) TableName() string {
	return "messages"
}