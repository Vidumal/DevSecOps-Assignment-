/*
 * Licensed under the Apache License, Version 2.0 (the “License”);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *         http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an “AS IS” BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package api

import (
	"crypto/tls"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"crapi.proj/goservice/api/config"
	"crapi.proj/goservice/api/router"
	"crapi.proj/goservice/api/seed"
	"github.com/gorilla/mux"
	"github.com/joho/godotenv"
)



func init() {
	// loads values from .env into the system
	if err := godotenv.Load(); err != nil {
		log.Print("Sad!! .env file not found")
	}
}

func identityServiceHealthCheck() {
	if os.Getenv("IDENTITY_SERVICE") == "" {
		time.Sleep(5 * time.Second)
		log.Fatal("IDENTITY_SERVICE is not set")
	}

	client := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		},
	}

	for attempts := 0; attempts <= 5; attempts++ {
		healthURL := fmt.Sprintf("http://%s/identity/health_check", os.Getenv("IDENTITY_SERVICE"))
		if os.Getenv("TLS_ENABLED") == "true" {
			healthURL = fmt.Sprintf("https://%s/identity/health_check", os.Getenv("IDENTITY_SERVICE"))
		}

		resp, err := client.Get(healthURL)
		if err != nil {
			log.Printf("Error while checking the health of identity service: %v", err)
			if attempts == 5 {
				log.Fatal("Identity service is not healthy. Terminating...")
			}
			log.Printf("Retrying in 5 seconds...")
			time.Sleep(5 * time.Second)
			continue
		}

		if resp.StatusCode == http.StatusOK {
			if err := resp.Body.Close(); err != nil {
				log.Println("Error closing response body:", err)
			}
			log.Printf("Identity service is healthy")
			time.Sleep(1 * time.Second)
			return
		}

		if err := resp.Body.Close(); err != nil {
			log.Println("Error closing response body:", err)
		}
		log.Printf("Identity service is not healthy: %v", resp.Status)
		if attempts == 5 {
			log.Fatal("Identity service is not healthy. Terminating...")
		}
		log.Printf("Retrying in 5 seconds...")
		time.Sleep(5 * time.Second)
	}

	log.Fatal("Identity service is not healthy. Terminating...")
}

func Run() {
	var server = config.Server{}
	var route = router.Server{}

	route.Client = server.InitializeMongo("mongodb", os.Getenv("MONGO_DB_USER"), os.Getenv("MONGO_DB_PASSWORD"), os.Getenv("MONGO_DB_PORT"), os.Getenv("MONGO_DB_HOST"))

	route.DB = server.Initialize("postgres", os.Getenv("DB_USER"), os.Getenv("DB_PASSWORD"), os.Getenv("DB_PORT"), os.Getenv("DB_HOST"), os.Getenv("DB_NAME"))

	identityServiceHealthCheck()

	seed.LoadMongoData(server.Client, server.DB)

	route.Router = mux.NewRouter()

	server.Router = route.InitializeRoutes()

	route.Run(":" + os.Getenv("SERVER_PORT"))

}
