package router
import (
	"fmt"
	"PgoAgent/config"

)	
func Run(){
	r:= SetupRouter()
	fmt.Println("4. Router has initilized")
	webServerAddr :=  fmt.Sprintf("%s:%d", config.ConfigHandler.WEBSERVER.Config.Host, config.ConfigHandler.WEBSERVER.Config.Port)
	fmt.Printf("5. PgoAgent Web server is running at http://%s\n", webServerAddr)
	r.Run(webServerAddr) // listen and serve on
}