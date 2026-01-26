package config

import (
    "fmt"
    "time"
    "go.uber.org/zap"
    "PgoAgent/log"
    "gorm.io/gorm"
    "PgoAgent/global"
    "gorm.io/driver/postgres"
    "PgoAgent/models"
)
func initDB() { //注意这个是小写只能在当前包使用，大写才能被其他包使用
    dsn := DSN
    db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{}) // 连接数据库 open ，gorm.Config是配置项
    if err != nil {
        log.L().Fatal("DataBase connection failed",
            zap.Error(err),
            zap.String("dsn", dsn),
        )
    }
    sqlDB, err := db.DB()
    if err != nil {
        log.L().Error("DataBase connection failed ,got error:", zap.Error(err))
    }
    sqlDB.SetMaxIdleConns(ConfigHandler.WEBSERVER.Config.MaxIdleConns) // 设置最大空闲连接数
    sqlDB.SetMaxOpenConns(ConfigHandler.WEBSERVER.Config.MaxOpenConns)
    sqlDB.SetConnMaxLifetime(time.Duration(ConfigHandler.WEBSERVER.Config.ConnMaxLifetime) * time.Hour)

    global.DB = db
    fmt.Println("1. DataBase connection success!")
}

func dbMigrate(){ //将go的结构体的类型迁移到数据库
    if err :=global.DB.AutoMigrate(
        &models.Users{},
        &models.Conversations{},
        &models.Messages{},
        );err != nil {
        log.L().Error("DataBase migration failed ,got error:", zap.Error(err))
    }
    fmt.Println("2. DataBase migration success!")
}