package utils
import "golang.org/x/crypto/bcrypt"

const cipher_number = 12 // 加密的计算伦茨

func HashPassword(pwd string) (string, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(pwd), cipher_number)
	return string(hash), err
}