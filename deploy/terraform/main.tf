terraform {
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}
# Minimal container deploy. Swap the provider block for aws_ecs_service,
# azurerm_container_app, or google_cloud_run_v2_service as needed.
provider "docker" {}
resource "docker_image" "readiness" { name = "ghcr.io/cognis-digital/readiness:latest" }
resource "docker_container" "readiness" {
  name  = "readiness"
  image = docker_image.readiness.image_id
  ports { internal = 8000 external = 8000 }
}
