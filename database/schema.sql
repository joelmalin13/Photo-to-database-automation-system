-- PIXELMIND: AI-Powered Visual Intelligence Database Schema
-- Compatible with MySQL 8.0+

CREATE DATABASE IF NOT EXISTS pixelmind CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pixelmind;

-- 1. Main images repository
CREATE TABLE IF NOT EXISTS images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    stored_path VARCHAR(500) NOT NULL,
    annotated_path VARCHAR(500) NULL,
    sha256 VARCHAR(64) NOT NULL UNIQUE,
    phash VARCHAR(64) NULL,
    width INT NOT NULL,
    height INT NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'Uncategorized',
    scene VARCHAR(100) NULL,
    environment VARCHAR(50) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_images_category (category),
    INDEX idx_images_scene (scene),
    INDEX idx_images_environment (environment),
    INDEX idx_images_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Detections per image (from YOLO)
CREATE TABLE IF NOT EXISTS detections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NOT NULL,
    label VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    count INT NOT NULL DEFAULT 1,
    avg_confidence FLOAT NOT NULL,
    bbox_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_detections_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    INDEX idx_detections_label (label),
    INDEX idx_detections_category (category),
    INDEX idx_detections_image_id (image_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Image DNA (fingerprint, colors, CLIP embedding)
CREATE TABLE IF NOT EXISTS image_dna (
    image_id INT PRIMARY KEY,
    dominant_colors_json JSON NULL,
    embedding_blob LONGBLOB NULL,
    composition_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dna_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Statistical anomaly flags
CREATE TABLE IF NOT EXISTS anomalies (
    image_id INT PRIMARY KEY,
    reason TEXT NOT NULL,
    score FLOAT NOT NULL DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_anomalies_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Audit & processing log
CREATE TABLE IF NOT EXISTS processing_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NULL,
    step VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    message TEXT NULL,
    execution_time_ms INT NOT NULL DEFAULT 0,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_log_image FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    INDEX idx_log_image_id (image_id),
    INDEX idx_log_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
