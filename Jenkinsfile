
pipeline {
    agent any

    options {
        timestamps()
    }

    environment {
        PYTHON = 'C:\\Users\\sangmesh\\AppData\\Local\\Programs\\Python\\Python312\\python.exe'
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Inventory Management - Source Checkout'
            }
        }

        stage('Check Python') {
            steps {
                bat '"%PYTHON%" --version'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '"%PYTHON%" -m pip install --upgrade pip'
                bat '"%PYTHON%" -m pip install -r requirements.txt'
            }
        }

        stage('Run Automated Tests') {
            steps {
                bat '"%PYTHON%" -m unittest discover -s tests -v'
            }
        }
    }

    post {
        success {
            echo 'SUCCESS: All automated tests passed!'
        }

        failure {
            echo 'FAILURE: Please check the build logs.'
        }

        always {
            echo 'Pipeline execution completed.'
        }
    }
}
