
pipeline {
    agent any

    options {
        timestamps()
    }

    stages {

        stage('Checkout') {
            steps {
                echo 'Inventory Management - Source Checkout'
            }
        }

        stage('Check Python') {
            steps {
                bat 'python --version'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat 'python -m pip install --upgrade pip'
                bat 'python -m pip install -r requirements.txt'
            }
        }

        stage('Run Automated Tests') {
            steps {
                bat 'python -m unittest discover -s tests -v'
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
