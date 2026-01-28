package config

import (
    "fmt"
    "time"
    "go.uber.org/zap"
    "gorm.io/gorm"
    "PgoAgent/global"
    "gorm.io/driver/postgres"
    "PgoAgent/models"
)
func initDB() { //注意这个是小写只能在当前包使用，大写才能被其他包使用
    dsn := DSN
    db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{}) // 连接数据库 open ，gorm.Config是配置项
    if err != nil {
        fmt.Println("DataBase connection failed",
            zap.Error(err),
            zap.String("dsn", dsn),
        )
        panic(err)
    }
    sqlDB, err := db.DB()
    if err != nil {
        fmt.Println("DataBase connection failed ,got error:", zap.Error(err))
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
        fmt.Println("DataBase migration failed ,got error:", zap.Error(err))
        panic(err)
    }
    fmt.Println("2. DataBase migration success!")
}